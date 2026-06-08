"""Stage 5: per-job tailored resume + cover letter.

Curated to *that exact posting*: the FULL job description is the primary input,
alongside the master resume and profile. The agent (OpenClaw model / Claude)
writes the drafts; this module assembles the task and saves the outputs.
"""
from __future__ import annotations

from typing import Any

from .config import output_dir
from .db import DB


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
        slug = f"{job['company']}_{job['title']}".replace("/", "-")[:60]
        (jdir / "resume.md").write_text(d.get("resume_markdown", ""), encoding="utf-8")
        (jdir / "cover_letter.md").write_text(d.get("cover_letter_markdown", ""), encoding="utf-8")
        why = d.get("why_fit", [])
        (jdir / "why_fit.md").write_text(
            "# Why this fits\n\n" + "\n".join(f"- {w}" for w in why), encoding="utf-8")
        (jdir / "_meta.md").write_text(
            f"# {job['title']} — {job['company']}\n\n{job['location']}\n\n{job['url']}\n",
            encoding="utf-8")
        db.set_state(jid, "docs_ready")
        n += 1
    return n
