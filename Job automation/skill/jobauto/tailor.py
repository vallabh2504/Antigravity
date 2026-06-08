"""Stage 5: per-job tailored resume + cover letter.

Curated to *that exact posting*: the FULL job description is the primary input,
alongside the master resume and profile. The agent (OpenClaw model / Claude)
writes the drafts; this module assembles the task and saves the outputs.
"""
from __future__ import annotations

from typing import Any

from .config import output_dir
from .db import DB


def build_apply_tasks(db: DB, profile: str, master_resume: str, top_n: int = 3) -> dict[str, Any]:
    """Scorer -> application-writer handoff: the TOP-N scored jobs only."""
    scored = [j for j in db.all()
              if j.get("score") is not None and j["state"] not in ("rejected",)]
    top = sorted(scored, key=lambda j: j.get("score") or 0, reverse=True)[:top_n]
    jobs = [{
        "id": j["id"], "company": j["company"], "title": j["title"],
        "location": j["location"], "url": j["url"],
        "full_jd": j["jd_text"], "fit_notes": j.get("score_json", {}),
        "score": j.get("score"),
    } for j in top]
    return {
        "handoff": "scorer -> application-writer sub-agent",
        "use_skills": ["resume-writer", "cover-letter-writer"],
        "instructions": (
            "You are the application-writer sub-agent. For EACH of these top-3 jobs, read "
            "full_jd + profile + master_resume + the two SKILL.md files, then write a curated, "
            "human-quality resume and cover letter (Markdown AND styled HTML from the skill "
            "templates). Ground everything in real experience; no fabrication; no AI boilerplate. "
            "Return a JSON list of {id, resume_markdown, resume_html, cover_letter_markdown, "
            "cover_letter_html, why_fit:[...]} as output/applications.json, then run "
            "`python -m jobauto apply-tailor output/applications.json`."
        ),
        "profile": profile,
        "master_resume": master_resume,
        "jobs": jobs,
    }


def build_tailor_tasks(db: DB, profile: str, master_resume: str,
                       states=("approved",)) -> dict[str, Any]:
    jobs = []
    for st in states:
        for job in db.by_state(st):
            jobs.append({
                "id": job["id"],
                "company": job["company"],
                "title": job["title"],
                "location": job["location"],
                "url": job["url"],
                "full_jd": job["jd_text"],          # FULL JD, not an excerpt
                "fit_notes": job.get("score_json", {}),
            })
    return {
        "instructions": (
            "For EACH job produce documents curated to THIS specific posting using its "
            "full_jd. Return {id, resume_markdown (reordered/emphasized bullets from the "
            "master resume that match this JD's requirements — do not invent experience), "
            "cover_letter_markdown (3-4 short paragraphs, addresses the JD's key needs, "
            "references the candidate's DLR/Bosch/Ecogenium fuel-cell work, mentions "
            "Stuttgart/Germany preference and visa status placeholder), why_fit (3 bullets)}."
        ),
        "profile": profile,
        "master_resume": master_resume,
        "jobs": jobs,
    }


def apply_tailor(db: DB, docs: list[dict]) -> int:
    n = 0
    out = output_dir()
    for d in docs:
        jid = d.get("id")
        job = db.get(jid) if jid else None
        if not job:
            continue
        jdir = out / jid
        jdir.mkdir(parents=True, exist_ok=True)
        (jdir / "resume.md").write_text(d.get("resume_markdown", ""), encoding="utf-8")
        (jdir / "cover_letter.md").write_text(d.get("cover_letter_markdown", ""), encoding="utf-8")
        if d.get("resume_html"):
            (jdir / "resume.html").write_text(d["resume_html"], encoding="utf-8")
        if d.get("cover_letter_html"):
            (jdir / "cover_letter.html").write_text(d["cover_letter_html"], encoding="utf-8")
        why = d.get("why_fit", [])
        (jdir / "why_fit.md").write_text(
            "# Why this fits\n\n" + "\n".join(f"- {w}" for w in why), encoding="utf-8")
        (jdir / "_meta.md").write_text(
            f"# {job['title']} — {job['company']}\n\n{job['location']}\n\n{job['url']}\n",
            encoding="utf-8")
        db.set_state(jid, "docs_ready")
        n += 1
    return n
