"""Regression tests for discovery dispatch, canonical dedupe, and eligibility scoring."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jobauto.db import DB
from jobauto.models import Job, RawPosting, canonicalize_url
from jobauto.normalize import ingest
from jobauto.score import heuristic_score
from jobauto.sources import Recipe
from jobauto.sources.fetch import fetch_recipe


class _Response:
    def __init__(self, payload, status_code=200, text=""):
        self.payload = payload
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8") if text else b""

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Client:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, *_args, **_kwargs):
        return _Response(self.payload)

    def post(self, *_args, **_kwargs):
        return _Response(self.payload)


class DiscoveryTests(unittest.TestCase):
    def test_aggregator_recipe_dispatches_to_aggregator_parser(self):
        recipe = Recipe("Arbeitnow", "agg_arbeitnow", "https://example.test/jobs")
        payload = {"data": [{
            "company_name": "Hydrogen AG", "title": "Fuel Cell Engineer",
            "location": "Stuttgart", "url": "https://example.test/job/1",
            "description": "Fuel cell controls", "created_at": "2026-07-01",
            "tags": ["hydrogen"],
        }]}
        with patch("jobauto.sources.fetch._client", return_value=_Client(payload)), \
             patch("jobauto.sources.aggregators.parse_aggregator") as parser:
            parser.return_value = [RawPosting("agg_arbeitnow", "Hydrogen AG", "Fuel Cell Engineer")]
            result = fetch_recipe(recipe)
        parser.assert_called_once()
        self.assertEqual(recipe, parser.call_args.args[0])
        self.assertEqual(payload, parser.call_args.args[1])
        self.assertIsInstance(parser.call_args.args[2], list)
        self.assertEqual(1, len(result))

    def test_custom_html_recipe_fetches_and_reports_empty_pages(self):
        from jobauto.sources.fetch import EmptySource
        recipe = Recipe("DLR", "custom", "https://example.test/careers")
        client = _Client({},)
        client.get = lambda *_args, **_kwargs: _Response({}, text="<html><body>Careers</body></html>")
        with self.assertRaises(EmptySource):
            from jobauto.sources.fetch import fetch_recipe_with
            fetch_recipe_with(recipe, client)

    def test_workday_recipe_and_parsing(self):
        from jobauto.sources import build_recipes, parse
        from jobauto.sources.workday import parse_workday, parse_workday_token
        host, tenant, board = parse_workday_token("abb.wd3.myworkdayjobs.com|abb|External_Career_Page")
        self.assertEqual("abb.wd3.myworkdayjobs.com", host)
        self.assertEqual("abb", tenant)
        self.assertEqual("External_Career_Page", board)

        recipes = build_recipes([{
            "name": "ABB",
            "portal": "workday",
            "token": "abb.wd3.myworkdayjobs.com|abb|External_Career_Page",
            "query": "hydrogen",
            "sectors": ["heavy"],
        }])
        self.assertEqual(1, len(recipes))
        r = recipes[0]
        self.assertEqual("POST", r.method)
        self.assertEqual("https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/External_Career_Page/jobs", r.list_url)
        self.assertEqual("hydrogen", r.body.get("searchText"))
        self.assertTrue(r.needs_detail)

        payload = {
            "jobPostings": [{
                "title": "Systems Engineer",
                "locationsText": "Stuttgart, Germany",
                "postedOn": "Posted 2 Days Ago",
                "externalPath": "/job/Stuttgart/Systems-Engineer_JR100",
                "bulletFields": ["JR100"],
            }]
        }
        postings = parse(r, payload)
        self.assertEqual(1, len(postings))
        p = postings[0]
        self.assertEqual("workday:ABB", p.source)
        self.assertEqual("ABB", p.company)
        self.assertEqual("Systems Engineer", p.title)
        self.assertEqual("Stuttgart, Germany", p.location)
        self.assertEqual("https://abb.wd3.myworkdayjobs.com/en-US/External_Career_Page/job/Stuttgart/Systems-Engineer_JR100", p.url)
        self.assertEqual("Posted 2 Days Ago", p.posted_at)
        self.assertEqual(["heavy"], p.extra.get("sectors"))

    def test_personio_recipe_and_parsing(self):
        from jobauto.sources import build_recipes, parse
        from jobauto.sources.personio import parse_personio
        recipes = build_recipes([{
            "name": "H2FLY",
            "portal": "personio",
            "token": "h2fly-gmbh",
            "sectors": ["aviation"],
        }])
        self.assertEqual(1, len(recipes))
        r = recipes[0]
        self.assertEqual("GET", r.method)
        self.assertEqual("https://h2fly-gmbh.jobs.personio.de/xml", r.list_url)

        xml_sample = """<?xml version="1.0" encoding="utf-8"?>
        <work-positions>
            <position>
                <id>123456</id>
                <name>Fuel Cell Test Engineer</name>
                <office>Stuttgart</office>
                <department>Powertrain</department>
                <employmentType>permanent</employmentType>
                <seniority>experienced</seniority>
                <schedule>full-time</schedule>
                <createdAt>2026-05-01T08:00:00+00:00</createdAt>
                <jobDescriptions>
                    <jobDescription>
                        <name>About the role</name>
                        <value><![CDATA[<p>Develop next-gen fuel cells.</p>]]></value>
                    </jobDescription>
                </jobDescriptions>
            </position>
        </work-positions>"""

        postings = parse(r, xml_sample)
        self.assertEqual(1, len(postings))
        p = postings[0]
        self.assertEqual("personio:H2FLY", p.source)
        self.assertEqual("H2FLY", p.company)
        self.assertEqual("Fuel Cell Test Engineer", p.title)
        self.assertEqual("Stuttgart, Powertrain", p.location)
        self.assertEqual("https://h2fly-gmbh.jobs.personio.de/job/123456?language=en", p.url)
        self.assertEqual("2026-05-01T08:00:00+00:00", p.posted_at)
        self.assertIn("Develop next-gen fuel cells.", p.jd_text)
        self.assertEqual(["aviation"], p.extra.get("sectors"))

    def test_tracking_urls_dedupe_and_existing_workflow_state_is_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            db = DB(Path(td) / "jobs.sqlite")
            first = RawPosting(
                "agg_adzuna", "Example GmbH", "Fuel Cell Controls Engineer", "Stuttgart",
                "https://adzuna.example/job/42?utm_source=newsletter&ref=abc", "Short JD", "",
            )
            self.assertEqual({"new": 1, "dup": 0}, ingest(db, [first]))
            job_id = db.all()[0]["id"]
            db.set_state(job_id, "approved")
            before = db.get(job_id)

            fuller = RawPosting(
                "greenhouse:example", "Example", "Fuel Cell Controls Engineer", "Stuttgart, Germany",
                "https://careers.example.com/jobs/42?utm_campaign=spring#apply",
                "Responsibilities and requirements. " * 40, "2026-07-09T08:00:00Z",
            )
            self.assertEqual({"new": 0, "dup": 1}, ingest(db, [fuller]))
            after = db.get(job_id)
            self.assertEqual(1, len(db.all()))
            self.assertEqual("approved", after["state"])
            self.assertEqual(before["first_seen"], after["first_seen"])
            self.assertGreater(len(after["jd_text"]), len(before["jd_text"]))
            self.assertEqual("2026-07-09T08:00:00Z", after["posted_at"])
            self.assertEqual("https://careers.example.com/jobs/42", after["url"])
            db.conn.close()

    def test_canonical_url_removes_tracking_but_keeps_job_identity_query(self):
        url = "https://WWW.Example.com/jobs/?id=42&utm_source=x&ref=mail#apply"
        self.assertEqual("https://example.com/jobs?id=42", canonicalize_url(url))


class ScoringTests(unittest.TestCase):
    def _job(self, title: str, jd: str, **extra):
        return {"id": "j1", "title": title, "jd_text": jd, "location": "Stuttgart",
                "posted_at": "2026-07-09T08:00:00Z", **extra}

    def test_german_prose_seniority_degree_and_security_are_exposed(self):
        jd = (
            "Fuel cell hydrogen system integration and Simulink controls. "
            "Responsibilities include stack modelling and test bench validation. "
            "Requirements: PhD required, fluent German, and EU citizenship required "
            "for security clearance. Apply by 31.08.2026. " * 8
        )
        result = heuristic_score(self._job("Senior Fuel Cell Engineer", jd), {})
        self.assertEqual("B2", result["german_required"])
        self.assertEqual("senior", result["seniority"])
        self.assertEqual("phd", result["degree_required"])
        self.assertFalse(result["visa_friendly_guess"])
        self.assertIn("citizenship_required", result["eligibility_flags"])
        self.assertIn("security_clearance", result["eligibility_flags"])
        self.assertEqual("exact", result["deadline_quality"])
        self.assertEqual("exact", result["posted_date_quality"])

    def test_thin_jd_and_senior_role_score_below_complete_entry_role(self):
        thin = heuristic_score(self._job("Senior Fuel Cell Engineer", "fuel cell"), {})
        complete_jd = (
            "Fuel cell PEM control simulation and stack system integration. "
            "Responsibilities include modelling and test bench work. "
            "Qualifications include a master's degree. Benefits and team details. " * 10
        )
        complete = heuristic_score(self._job("Graduate Fuel Cell Engineer", complete_jd), {})
        self.assertEqual("thin", thin["jd_completeness"])
        self.assertEqual("complete", complete["jd_completeness"])
        self.assertGreater(complete["score"], thin["score"])
        self.assertIsNone(complete["visa_friendly_guess"])

    def test_postgraduate_degree_and_silent_visa_status_are_not_misclassified(self):
        jd = (
            "Responsibilities include Python-based prescriptive maintenance analysis for "
            "fuel-cell aircraft and deriving system design requirements. Qualifications: "
            "a postgraduate engineering degree, very good English, and "
            "German is desirable. The role is based in Hamburg. " * 8
        )
        result = heuristic_score(self._job("Graduate Engineer", jd), {})
        self.assertEqual("master", result["degree_required"])
        self.assertIsNone(result["visa_friendly_guess"])

    @unittest.skipUnless((Path(__file__).resolve().parents[1] / "profile" / "config.yml").is_file(),
                         "private operator filtering defaults are not part of a public export")
    def test_hard_filter_and_heuristic_score_german_geographic_scoping(self):
        from jobauto.score import hard_filter, heuristic_score
        from jobauto.config import load_config
        cfg = load_config()

        self.assertIn("de", cfg.get("target_countries", []))
        self.assertNotIn("europe", cfg.get("search_locations", []))
        self.assertIn("farmington hills", cfg.get("excluded_locations", []))

        de_jobs = [
            {"id": "1", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Stuttgart, Germany"},
            {"id": "2", "title": "Hydrogen Engineer", "jd_text": "hydrogen fuel cell", "location": "Munich, Bavaria, Germany"},
            {"id": "3", "title": "Fuel Cell Systems Engineer", "jd_text": "fuel cell stack", "location": "Aachen, North Rhine-Westphalia"},
            {"id": "4", "title": "Electrolysis Specialist", "jd_text": "electrolyzer hydrogen", "location": "Berlin, DE"},
            {"id": "5", "title": "Fuel Cell Developer", "jd_text": "brennstoffzelle wasserstoff", "location": "Remote"},
            {"id": "6", "title": "Fuel Cell Developer", "jd_text": "brennstoffzelle", "location": "Wendlingen am Neckar, Baden-Württemberg"},
            {"id": "7", "title": "Simulation Engineer", "jd_text": "PEM fuel cell model", "location": "Renningen, Baden-Württemberg, Germany"},
            {"id": "8", "title": "Test Engineer", "jd_text": "fuel cell test bench", "location": "Eresing, Bavaria, Germany"},
            {"id": "9", "title": "Stack Engineer", "jd_text": "fuel cell stack", "location": "Schwieberdingen, Baden-Württemberg, Germany"},
        ]
        for j in de_jobs:
            keep, reason = hard_filter(j, cfg)
            self.assertTrue(keep, f"Expected {j['location']} to pass hard_filter, got: {reason}")
            score_res = heuristic_score(j, cfg)
            self.assertGreater(score_res["score"], 0)

        foreign_jobs = [
            {"id": "f1", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Farmington Hills, United States"},
            {"id": "f2", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Wuxi, China"},
            {"id": "f3", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Bangalore, India"},
            {"id": "f4", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Singapore, Singapore"},
            {"id": "f5", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Budapest, Hungary"},
            {"id": "f6", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Lincolnton, NC, US"},
            {"id": "f7", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Shanghai, cn"},
            {"id": "f8", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Tokyo, Japan"},
            {"id": "f9", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "Paris, France"},
            {"id": "f10", "title": "Fuel Cell Engineer", "jd_text": "PEM fuel cell", "location": "London, UK"},
        ]
        for j in foreign_jobs:
            keep, reason = hard_filter(j, cfg)
            self.assertFalse(keep, f"Expected {j['location']} to be dropped by hard_filter")
            self.assertTrue("outside the target" in reason or "profile exclusion" in reason)
            score_res = heuristic_score(j, cfg)
            self.assertEqual(0, score_res["score"])
            self.assertTrue(any("outside the target" in r or "profile exclusion" in r
                                for r in score_res["reasons"]))

    def test_non_german_profile_and_unknown_city_are_not_personalized(self):
        from jobauto.score import hard_filter

        french_profile = {
            "include_keywords": ["embedded software"],
            "target_countries": ["fr"],
            "search_locations": ["Paris, France"],
        }
        keep, _ = hard_filter({"title": "Embedded Software Engineer",
                               "jd_text": "Develop firmware", "location": "Paris, France"},
                              french_profile)
        self.assertTrue(keep)

        neutral_profile = {"include_keywords": ["embedded software"],
                           "target_countries": []}
        keep, reason = hard_filter({"title": "Embedded Software Engineer",
                                    "jd_text": "Develop firmware", "location": "Kassel"},
                                   neutral_profile)
        self.assertTrue(keep, reason)


class SourcePolicyTests(unittest.TestCase):
    def test_registry_is_complete_and_prohibited_sources_are_inert(self):
        from jobauto.sources.registry import REGISTRY, PROHIBITED, validate_registry, is_enabled
        self.assertEqual([], validate_registry())
        self.assertTrue(all(info.terms_url.startswith("http") for info in REGISTRY.values()))
        self.assertFalse(is_enabled("adzuna", {"enabled": True}))
        self.assertEqual(PROHIBITED, REGISTRY["adzuna"].commercial_use)

    def test_three_zero_yield_records_are_flagged_and_history_is_append_only(self):
        from jobauto.sources.health import SourceRun, append_history, read_history, zero_yield_sources
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "source_history.jsonl"
            records = []
            for idx in range(3):
                run = SourceRun(run_id=f"run{idx}")
                records.append(run.record("custom:Example", attempted=True, ok=False,
                                          jobs_yielded=0, status="empty", error="no postings"))
            append_history(records[:2], path)
            append_history(records[2:], path)
            self.assertEqual(3, len(read_history(path)))
            self.assertEqual(["custom:Example"], zero_yield_sources(path))
            self.assertEqual({"run_id", "utc", "source", "attempted", "ok", "failed",
                              "jobs_yielded"}, set(read_history(path)[0]))


if __name__ == "__main__":
    unittest.main()
