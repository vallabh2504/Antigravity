"""Application kit, gates and dashboard.

No agent, browser or rendercv is used: the tests write the files the roles would
write and check what the gates decide.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from jobauto.db import DB
from jobauto.models import Job, now_iso
from jobauto.writer import facts, gates, kit
from jobauto.writer.agents import ClaudeCliRunner
from jobauto.writer.plan import validate_plan

JD = ("You will assemble laboratory-scale electrochemical cells and execute test protocols. "
      "Knowledge of electrochemical systems, including electrolyzers, fuel cells, and batteries. ") * 12
MASTER = ("name: Test Candidate\nemail: test@example.org\nexperience:\n  - bullets:\n"
          "    - Built a standalone fuel-cell test bench and ran polarization curves.\n")


def good_plan() -> dict:
    return {
        "fit": {"verdict": "partial", "reason": "Fuel-cell testing, no electrolyzer work."},
        "requirements": [
            {"kind": "responsibility", "quote": "assemble laboratory-scale electrochemical cells", "status": "partial",
             "evidence": [{"fact_quote": "standalone fuel-cell test bench", "why": "hands-on test hardware"}]},
            {"kind": "must", "quote": "Knowledge of electrochemical systems", "status": "supported",
             "evidence": [{"fact_quote": "ran polarization curves", "why": "stack characterisation"}]},
            {"kind": "nice", "quote": "electrolyzers", "status": "gap", "evidence": []},
        ],
        "keywords": [{"term": "test protocols", "resume_wording": "test procedures",
                      "fact_quote": "ran polarization curves"}],
        "angle": "Hands-on fuel-cell testing transfers to electrolysis cells.",
        "experience_emphasis": [], "operator_questions": ["Earliest start date?"], "do_not_claim": ["electrolyzer work"],
    }


class PlanValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        base = Path(self.tmp.name)
        (base / "master_resume.yml").write_text(MASTER, encoding="utf-8")
        self.corpus = facts.load_fact_corpus(base)
        self.job = {"jd_text": JD}

    def tearDown(self):
        self.tmp.cleanup()

    def test_verbatim_plan_passes(self):
        self.assertEqual(validate_plan(good_plan(), self.job, self.corpus), [])

    def test_invented_quotes_are_caught(self):
        plan = good_plan()
        plan["requirements"][0]["quote"] = "five years of electrolyzer stack design"
        plan["requirements"][1]["evidence"][0]["fact_quote"] = "led an electrolyzer durability campaign"
        messages = [f.message for f in validate_plan(plan, self.job, self.corpus)]
        self.assertTrue(any("not found verbatim in the job description" in m for m in messages))
        self.assertTrue(any("not found verbatim in the facts" in m for m in messages))


class JudgeTests(unittest.TestCase):
    settings = kit.settings_from_config({})
    manifest = {"sha256": {"resume": "aa", "cover_letter": "bb"}}

    def review(self, **over):
        base = {"content_score": 94, "design_score": 92, "pass": True, "findings": [],
                "reviewed_pdf_sha256": {"resume": "aa", "cover_letter": "bb"}}
        return {**base, **over}

    def test_bound_passing_review_passes(self):
        self.assertEqual(gates.judge(self.review(), self.manifest, self.settings), (True, []))

    def test_low_score_major_finding_self_fail_and_unbound_review_fail(self):
        for bad in (self.review(design_score=80), self.review(findings=[{"severity": "major"}]),
                    self.review(reviewed_pdf_sha256={"resume": "zz", "cover_letter": "bb"}),
                    self.review(**{"pass": False})):
            passed, reasons = gates.judge(bad, self.manifest, self.settings)
            self.assertFalse(passed)
            self.assertTrue(reasons)

    def test_weak_fit_and_eligibility_gap_hold(self):
        plan = good_plan()
        self.assertEqual(gates.hold_reasons(plan), [])
        plan["fit"]["verdict"] = "weak"
        plan["requirements"].append({"kind": "eligibility", "quote": "EU work permit", "status": "gap"})
        self.assertEqual(len(gates.hold_reasons(plan)), 2)


class KitTests(unittest.TestCase):
    def setUp(self):
        # The dashboard opens its own connections; Windows keeps the file locked until they are collected.
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.home = Path(self.tmp.name)
        (self.home / "profile").mkdir()
        (self.home / "profile" / "master_resume.yml").write_text(MASTER, encoding="utf-8")
        self.old = os.environ.get("JOBAUTO_HOME")
        os.environ["JOBAUTO_HOME"] = str(self.home)
        (self.home / "output").mkdir()
        self.db = DB(self.home / "output" / "jobs.db")
        self.db.upsert(Job(id="job1", source="test", company="Example GmbH", title="Test Engineer",
                           location="Berlin", url="https://example.org/job1", jd_text=JD,
                           posted_at="2026-09-01", first_seen=now_iso()))
        self.job_id = self.db.all()[0]["id"]
        self.db.set_state(self.job_id, "approved", force=True)

    def tearDown(self):
        if self.old is None:
            os.environ.pop("JOBAUTO_HOME", None)
        else:
            os.environ["JOBAUTO_HOME"] = self.old
        self.db.conn.close()
        self.tmp.cleanup()

    def test_prepare_writes_kit_and_prompt(self):
        out = kit.prepare(self.db.get(self.job_id))
        ws, app = Path(out["workspace"]), Path(out["app_dir"])
        for rel in ("roles/planner.md", "roles/writer.md", "roles/reviewer.md", "job/job.md",
                    "facts/master_resume.yml", "schema/content_schema.json", "skills/application-reviewer/SKILL.md",
                    "examples/content.json"):
            self.assertTrue((ws / rel).is_file(), rel)
        prompt = (app / "PROMPT.md").read_text(encoding="utf-8")
        self.assertIn("check-plan", prompt)
        self.assertIn("finalize", prompt)
        self.assertEqual(kit.load_status(app)["stage"], "prepared")

    def test_placeholder_resume_is_refused(self):
        (self.home / "profile" / "master_resume.yml").write_text("name: Your Name\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            kit.prepare(self.db.get(self.job_id))

    def test_check_plan_feedback_then_pass(self):
        out = kit.prepare(self.db.get(self.job_id))
        ws = Path(out["workspace"])
        bad = good_plan()
        bad["requirements"][0]["quote"] = "invented requirement text here"
        (ws / "plan.json").write_text(json.dumps(bad), encoding="utf-8")
        self.assertEqual(gates.check_plan(out["app_dir"], self.db)["result"], "fix_plan")
        self.assertTrue((ws / "FEEDBACK.md").is_file())
        (ws / "plan.json").write_text(json.dumps(good_plan()), encoding="utf-8")
        self.assertEqual(gates.check_plan(out["app_dir"], self.db)["result"], "plan_ok")
        self.assertFalse((ws / "FEEDBACK.md").exists())
        self.assertEqual(gates.summary(self.job_id)["questions"], ["Earliest start date?"])

    def test_finalize_refuses_before_render(self):
        out = kit.prepare(self.db.get(self.job_id))
        self.assertFalse(gates.finalize(out["app_dir"], self.db)["ok"])

    def test_dashboard_prepare_needs_token_and_returns_prompt(self):
        from fastapi.testclient import TestClient

        from jobauto import dashboard

        client = TestClient(dashboard.app)
        self.assertEqual(client.get("/api/jobs").json()["jobs"][0]["id"], self.job_id)
        url = f"/api/jobs/{self.job_id}/prepare"
        self.assertEqual(client.post(url, json={}).status_code, 403)
        response = client.post(url, json={}, headers={"X-Token": dashboard.TOKEN})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("planner", response.json()["prompt"])
        self.assertIn(dashboard.TOKEN, client.get("/").text)


class RunnerTests(unittest.TestCase):
    def test_headless_command_resumes_its_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            argv = ClaudeCliRunner(command="claude", model="opus")._argv("abc", Path(tmp))
        self.assertIn("--resume", argv)

    def test_template_names_are_parsed(self):
        self.assertEqual(kit.parse_templates(["rendercv-sb2nov", "html-karla-navy"]), (["karla-navy"], ["sb2nov"]))
        with self.assertRaises(ValueError):
            kit.parse_templates(["sb2nov"])


if __name__ == "__main__":
    unittest.main()
