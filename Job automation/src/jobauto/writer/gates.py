"""The code gates between the roles.  Agents run them; they never judge themselves.

Each gate returns a dict with ``result`` (a short word), ``ok``, details, and
``next`` (one instruction for the orchestrating agent), records itself in
``status.json``, and writes ``FEEDBACK.md`` for the role that has to act.

* ``check_plan`` - every quote in ``plan.json`` found verbatim.
* ``render``     - fact lock, rendering in the chosen templates, PDF QA; the
  round's PDFs and their SHA-256 go into ``rounds/rN/``.
* ``finalize``   - the pass rule applied to ``review.json``, bound to the PDFs of
  the round; on a pass the upload-named PDFs are copied to ``final/``.
"""
from __future__ import annotations

import datetime as _dt
import shutil
from pathlib import Path
from typing import Any

from ..db import DB
from . import SCHEMA
from .facts import load_fact_corpus
from .kit import (TERMINAL, load_status, log_event, read_json, resolve, save_status, settings_from_config,
                  sha256, workspace_of, write_json, parse_templates)
from .plan import validate_plan
from .render import render_suite


def _job(app_dir: Path, ws: Path) -> dict[str, Any]:
    job, _ = read_json(app_dir / "job.json")
    job = dict(job or {})
    job_md = ws / "job" / "job.md"
    if job_md.is_file():
        # The workspace copy is the source of truth: the candidate may have pasted the full posting there.
        job["jd_text"] = job_md.read_text(encoding="utf-8")
    return job


def _feedback(ws: Path, title: str, items: list[str]) -> None:
    lines = [f"# {title}", ""] + [f"- {item}" for item in items]
    (ws / "FEEDBACK.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _clear_feedback(ws: Path) -> None:
    (ws / "FEEDBACK.md").unlink(missing_ok=True)


def _set_state(db: DB | None, job_id: str, state: str) -> None:
    if db is None:
        return
    job = db.get(job_id)
    if job and job["state"] != state:
        try:
            db.set_state(job_id, state)
        except ValueError:
            pass  # the candidate moved the job on by hand; the documents still count


def _finished(status: dict[str, Any]) -> dict[str, Any] | None:
    if status.get("result") in TERMINAL:
        return {"result": status["result"], "ok": status["result"] == "docs_ready",
                "next": f"This application already finished with {status['result']}. Report it. To start over, "
                        f"run `jobauto app prepare {status.get('job_id')} --redo`."}
    return None


def _questions_md(job: dict[str, Any], plan: dict[str, Any]) -> str:
    questions = [q for q in plan.get("operator_questions") or [] if str(q).strip()]
    fit = plan.get("fit") or {}
    lines = [f"# Open questions: {job.get('company')} - {job.get('title')}", ""]
    lines += [f"- {q}" for q in questions] or ["None."]
    lines += ["", "Answer them in `profile/writer_answers.md`. The next run uses the answers as facts.", "",
              f"Fit verdict: **{fit.get('verdict')}** - {fit.get('reason')}"]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------ check-plan

def check_plan(ref: str | Path, db: DB | None = None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or settings_from_config()
    app_dir = resolve(ref)
    ws, status = workspace_of(app_dir), load_status(app_dir)
    if (done := _finished(status)):
        return done
    job = _job(app_dir, ws)
    plan, problem = read_json(ws / "plan.json")
    findings = [{"where": "plan.json", "message": problem}] if problem else \
        [f.as_dict() for f in validate_plan(plan, job, load_fact_corpus())]
    status["attempts"]["plan"] = status["attempts"].get("plan", 0) + 1
    if findings:
        _feedback(ws, "Feedback for the planner: plan.json failed the plan gate",
                  [f"{f['where']}: {f['message']}" for f in findings])
        log_event(status, "check-plan", False, f"{len(findings)} finding(s)")
        exhausted = status["attempts"]["plan"] > settings["max_fix_attempts"]
        if exhausted:
            status.update(result="needs_operator", reason="plan gate failed too often")
        save_status(app_dir, status)
        return {"result": "needs_operator" if exhausted else "fix_plan", "ok": False, "findings": findings,
                "next": "Stop and report the findings to the person." if exhausted else
                "Send the planner back: it reads FEEDBACK.md. Then run check-plan again."}
    _clear_feedback(ws)
    write_json(app_dir / "plan.json", plan)
    (app_dir / "questions.md").write_text(_questions_md(job, plan), encoding="utf-8")
    status.update(stage="planned", plan_sha256=sha256(ws / "plan.json"), fit=plan.get("fit"),
                  questions=plan.get("operator_questions") or [])
    log_event(status, "check-plan", True, f"fit {(plan.get('fit') or {}).get('verdict')}")
    save_status(app_dir, status)
    return {"result": "plan_ok", "ok": True, "fit": plan.get("fit"),
            "questions": plan.get("operator_questions") or [],
            "next": "Run the writer (roles/writer.md), then run the render gate."}


# ---------------------------------------------------------------------------- render

def _letter_date(today: _dt.date | None = None) -> str:
    today = today or _dt.date.today()
    return f"{today.day} {today.strftime('%B %Y')}"


def _machine_problems(report: dict[str, Any]) -> list[dict[str, str]]:
    problems = [{"where": f["where"], "message": f["message"]} for f in report["validation"] if f["level"] == "error"]
    for t in report.get("templates", []):
        name = f"{t['engine']}-{t['theme']}"
        for msg in t.get("resume", {}).get("problems", []) + t.get("cover_letter", {}).get("problems", []):
            problems.append({"where": name, "message": msg})
        if t.get("error"):
            problems.append({"where": name, "message": t["error"]})
    return problems


def render(ref: str | Path, db: DB | None = None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or settings_from_config()
    app_dir = resolve(ref)
    ws, status = workspace_of(app_dir), load_status(app_dir)
    if (done := _finished(status)):
        return done
    job = _job(app_dir, ws)

    plan, problem = read_json(ws / "plan.json")
    plan_findings = [{"where": "plan.json", "message": problem}] if problem else \
        [f.as_dict() for f in validate_plan(plan, job, load_fact_corpus())]
    if plan_findings or status.get("stage") == "prepared":
        return {"result": "fix_plan", "ok": False, "findings": plan_findings,
                "next": "The plan has not passed check-plan. Run the planner and check-plan first."}

    content, problem = read_json(ws / "content.json")
    if problem or not isinstance(content, dict):
        problems = [{"where": "content.json", "message": problem or "content.json must be a JSON object"}]
        return _render_failed(app_dir, ws, status, settings, problems)
    if status.get("reviewed_content_sha256") and sha256(ws / "content.json") == status["reviewed_content_sha256"]:
        problems = [{"where": "content.json", "message": "content.json was not revised after the last review"}]
        return _render_failed(app_dir, ws, status, settings, problems)

    content["schema"] = SCHEMA
    content["job"] = {"id": job.get("id"), "company": job.get("company"), "title": job.get("title"),
                      "location": job.get("location")}
    content.setdefault("resume", {})["pages"] = int(settings.get("resume_pages", 2))
    content.setdefault("cover_letter", {})["date"] = _letter_date()
    write_json(ws / "content.json", content)

    html, rcv = parse_templates(settings["templates"])
    try:
        report = render_suite(content, job, app_dir / "templates", html_themes=html, rendercv_themes=rcv)
    except Exception as exc:  # a malformed content.json must come back as feedback, not a traceback
        return _render_failed(app_dir, ws, status, settings,
                              [{"where": "content.json", "message": f"{type(exc).__name__}: {exc}"}])
    problems = _machine_problems(report)
    if report["status"] == "validation_failed" or problems:
        return _render_failed(app_dir, ws, status, settings, problems)

    round_dir = ws / "rounds" / f"r{status['round']}"
    primary = report["templates"][0]
    if round_dir.exists():
        shutil.rmtree(round_dir)
    (round_dir / "previews").mkdir(parents=True)
    shutil.copy2(primary["resume"]["pdf"], round_dir / "resume.pdf")
    shutil.copy2(primary["cover_letter"]["pdf"], round_dir / "cover_letter.pdf")
    for png in primary.get("previews", []):
        shutil.copy2(png, round_dir / "previews" / Path(png).name)
    warnings = [f"{f['where']}: {f['message']}" for f in report["validation"] if f["level"] != "error"]
    if not primary.get("previews"):
        warnings.append("no page images: install Poppler (pdftoppm) so the reviewer can see the layout; "
                        "until then the reviewer reads the PDFs only")
    template = f"{primary['engine']}-{primary['theme']}"
    write_json(round_dir / "render_report.json", {"template": template, "resume": primary["resume"],
                                                  "cover_letter": primary["cover_letter"], "warnings": warnings})
    manifest = {"round": status["round"], "template": template,
                "sha256": {"resume": sha256(round_dir / "resume.pdf"),
                           "cover_letter": sha256(round_dir / "cover_letter.pdf")}}
    write_json(round_dir / "manifest.json", manifest)
    (ws / "round.txt").write_text(f"rounds/r{status['round']}\n", encoding="utf-8")
    (ws / "review.json").unlink(missing_ok=True)
    _clear_feedback(ws)
    write_json(app_dir / "content.json", content)

    status.update(stage="rendered", manifest={**manifest, "template_dir": primary["dir"]},
                  content_sha256=sha256(ws / "content.json"))
    status["attempts"]["render"] = 0
    log_event(status, "render", True, f"round {status['round']} rendered in {template}")
    save_status(app_dir, status)
    _set_state(db, job.get("id", ""), "docs_review")
    return {"result": "rendered", "ok": True, "round": status["round"], "round_dir": f"rounds/r{status['round']}",
            "warnings": warnings,
            "next": "Run the reviewer (roles/reviewer.md) - never the agent that wrote content.json - "
                    "then run the finalize gate."}


def _render_failed(app_dir: Path, ws: Path, status: dict[str, Any], settings: dict[str, Any],
                   problems: list[dict[str, str]]) -> dict[str, Any]:
    status["attempts"]["render"] = status["attempts"].get("render", 0) + 1
    _feedback(ws, f"Feedback for the writer: the render gate failed (round {status['round']})",
              [f"{p['where']}: {p['message']}" for p in problems])
    log_event(status, "render", False, f"round {status['round']}: {len(problems)} problem(s)")
    exhausted = status["attempts"]["render"] > settings["max_fix_attempts"]
    if exhausted:
        status.update(result="needs_operator", reason="render gate failed too often")
    save_status(app_dir, status)
    return {"result": "needs_operator" if exhausted else "fix_content", "ok": False, "problems": problems,
            "next": "Stop and report the problems to the person." if exhausted else
            "Send the writer back: it reads FEEDBACK.md and rewrites content.json. Then run render again."}


# -------------------------------------------------------------------------- finalize

def judge(review: Any, manifest: dict[str, Any], settings: dict[str, Any]) -> tuple[bool, list[str]]:
    """The pass rule lives here, not in the reviewer's own ``pass`` flag."""
    if not isinstance(review, dict):
        return False, ["review.json is not a JSON object"]
    reasons = []
    mins = settings["min_scores"]
    try:
        content_score, design_score = int(review.get("content_score", 0)), int(review.get("design_score", 0))
    except (TypeError, ValueError):
        content_score = design_score = 0
        reasons.append("scores are not integers")
    if content_score < mins["content"]:
        reasons.append(f"content_score {content_score} < {mins['content']}")
    if design_score < mins["design"]:
        reasons.append(f"design_score {design_score} < {mins['design']}")
    findings = review.get("findings") if isinstance(review.get("findings"), list) else []
    serious = [f for f in findings if isinstance(f, dict) and str(f.get("severity", "")).lower() in ("blocker", "major")]
    if serious:
        reasons.append(f"{len(serious)} blocker/major finding(s) open")
    if review.get("pass") is not True:
        reasons.append("the reviewer did not pass it")
    bound = review.get("reviewed_pdf_sha256") if isinstance(review.get("reviewed_pdf_sha256"), dict) else {}
    if any(str(bound.get(k, "")).lower() != v for k, v in manifest["sha256"].items()):
        reasons.append("the review is not bound to this round's PDFs (reviewed_pdf_sha256 does not match manifest.json)")
    return not reasons, reasons


def hold_reasons(plan: Any) -> list[str]:
    if not isinstance(plan, dict):
        return []
    reasons = []
    fit = plan.get("fit") or {}
    if fit.get("verdict") == "weak":
        reasons.append(f"fit is weak: {fit.get('reason')}")
    for req in plan.get("requirements") or []:
        if isinstance(req, dict) and req.get("kind") == "eligibility" and req.get("status") == "gap":
            reasons.append(f"eligibility requirement not met: {req.get('quote')}")
    return reasons


def _copy_final(app_dir: Path, manifest: dict[str, Any]) -> list[str]:
    final = app_dir / "final"
    if final.exists():
        shutil.rmtree(final)
    final.mkdir(parents=True)
    wanted = set(manifest["sha256"].values())
    copied = []
    for pdf in sorted(Path(manifest["template_dir"]).glob("*.pdf")):
        if pdf.name in ("resume.pdf", "cover_letter.pdf") or sha256(pdf) not in wanted:
            continue
        shutil.copy2(pdf, final / pdf.name)
        copied.append(str(final / pdf.name))
    return copied


def finalize(ref: str | Path, db: DB | None = None, settings: dict[str, Any] | None = None) -> dict[str, Any]:
    settings = settings or settings_from_config()
    app_dir = resolve(ref)
    ws, status = workspace_of(app_dir), load_status(app_dir)
    if (done := _finished(status)):
        return done
    if status.get("stage") != "rendered" or not status.get("manifest"):
        return {"result": "render_first", "ok": False,
                "next": "There is no rendered round waiting for review. Run the writer and the render gate first."}
    manifest = status["manifest"]
    round_no = manifest["round"]
    round_dir = ws / "rounds" / f"r{round_no}"
    for kind, digest in manifest["sha256"].items():
        pdf = round_dir / f"{kind}.pdf"
        if not pdf.is_file() or sha256(pdf) != digest:
            return {"result": "render_first", "ok": False,
                    "next": f"{pdf.name} in rounds/r{round_no} changed after rendering. Run the render gate again."}

    review_path = ws / "review.json" if (ws / "review.json").is_file() else round_dir / "review.json"
    review, problem = read_json(review_path)
    if problem:
        return {"result": "review_missing", "ok": False, "problem": problem,
                "next": "Run the reviewer: it must write review.json in the workspace root. Then run finalize."}

    passed, reasons = judge(review, manifest, settings)
    write_json(app_dir / "reviews" / f"round_{round_no}.json", review)
    write_json(ws / "reviews" / f"round_{round_no}.json", review)
    review_path.unlink(missing_ok=True)
    scores = {"round": round_no, "content": review.get("content_score") if isinstance(review, dict) else None,
              "design": review.get("design_score") if isinstance(review, dict) else None,
              "passed": passed, "reasons": reasons}
    status["reviews"] = [r for r in status.get("reviews", []) if r.get("round") != round_no] + [scores]
    job_id = status.get("job_id", "")

    if passed:
        _clear_feedback(ws)
        plan, _ = read_json(ws / "plan.json")
        holds = hold_reasons(plan) if settings.get("hold_on_weak_fit", True) else []
        final = _copy_final(app_dir, manifest)
        result = "hold" if holds else "docs_ready"
        status.update(stage="done", result=result, final_pdfs=final, hold_reasons=holds,
                      finished_at=_dt.datetime.now().isoformat(timespec="seconds"))
        log_event(status, "finalize", True, f"round {round_no} passed" + (f"; held: {'; '.join(holds)}" if holds else ""))
        save_status(app_dir, status)
        _set_state(db, job_id, "docs_ready" if result == "docs_ready" else "docs_review")
        return {"result": result, "ok": True, "scores": scores, "final_pdfs": final, "hold_reasons": holds,
                "next": ("Done. Report the final PDFs, the review scores and questions.md to the person."
                         if result == "docs_ready" else
                         "Stop. The documents passed review, but the candidate must decide: report the hold "
                         "reasons, the final PDFs and questions.md.")}

    status["reviewed_content_sha256"] = status.get("content_sha256")
    if round_no >= settings["max_review_rounds"]:
        status.update(stage="done", result="needs_operator", reason=f"not accepted after {round_no} review round(s)")
        log_event(status, "finalize", False, f"round {round_no}: {'; '.join(reasons)}")
        save_status(app_dir, status)
        return {"result": "needs_operator", "ok": False, "scores": scores, "reasons": reasons,
                "next": "Stop. Report the last review (reviews/) and why it did not pass to the person."}

    items = [f"not accepted: {r}" for r in reasons]
    for f in (review.get("findings") or []) if isinstance(review, dict) else []:
        if isinstance(f, dict):
            items.append(f"[{f.get('severity')}] {f.get('where')}: {f.get('issue')} -> fix: {f.get('fix')}")
    _feedback(ws, f"Feedback for the writer: review round {round_no} (full review in reviews/round_{round_no}.json)",
              items)
    status.update(stage="planned", round=round_no + 1)
    log_event(status, "finalize", False, f"round {round_no}: {'; '.join(reasons)}")
    save_status(app_dir, status)
    return {"result": "revise", "ok": False, "scores": scores, "reasons": reasons,
            "next": "Send the writer back (it reads FEEDBACK.md and rewrites content.json), run render, run the "
                    "same reviewer again, then finalize."}


# ---------------------------------------------------------------------------- status

def summary(ref: str | Path) -> dict[str, Any]:
    app_dir = resolve(ref)
    status = load_status(app_dir)
    return {"app_dir": str(app_dir), "job_id": status.get("job_id"), "company": status.get("company"),
            "title": status.get("title"), "stage": status.get("stage"), "result": status.get("result"),
            "round": status.get("round"), "fit": status.get("fit"), "questions": status.get("questions", []),
            "reviews": status.get("reviews", []), "final_pdfs": status.get("final_pdfs", []),
            "hold_reasons": status.get("hold_reasons", []), "warnings": status.get("warnings", []),
            "last_event": (status.get("history") or [None])[-1]}
