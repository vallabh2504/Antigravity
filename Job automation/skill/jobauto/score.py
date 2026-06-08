"""Stage 3: rules prefilter + LLM-scoring exchange.

The LLM scoring itself is done by the agent (OpenClaw's model, or Claude in this
container) — see SKILL.md. This module produces the task list the agent scores
and applies the results back to the DB.
"""
from __future__ import annotations

from typing import Any

from .db import DB


def hard_filter(job: dict, cfg: dict) -> tuple[bool, str]:
    """Cheap rules to drop obvious misses before spending LLM calls."""
    text = f"{job['title']} {job['jd_text']}".lower()
    inc = [k.lower() for k in cfg.get("include_keywords", [])]
    if inc and not any(k in text for k in inc):
        return False, "no fuel-cell/hydrogen keyword"
    excl = [k.lower() for k in cfg.get("exclude_keywords", [])]
    if any(k in text for k in excl):
        return False, "excluded keyword"
    locs = [l.lower() for l in cfg.get("locations", [])]
    loc = (job.get("location") or "").lower()
    if locs and loc and not any(l in loc for l in locs):
        # don't hard-drop remote/unspecified; only drop clearly-elsewhere
        if "remote" not in loc and loc.strip():
            return False, f"location '{job['location']}' outside target"
    return True, "passed rules"


def build_score_tasks(db: DB, cfg: dict, profile: str, limit: int = 50) -> dict[str, Any]:
    """Emit unscored jobs (after rules) for the agent to LLM-score."""
    tasks = []
    dropped = []
    for job in db.unscored():
        keep, reason = hard_filter(job, cfg)
        if not keep:
            db.set_score(job["id"], 0, {"reasons": [reason], "tier": "filtered"})
            dropped.append({"id": job["id"], "reason": reason})
            continue
        tasks.append({
            "id": job["id"],
            "company": job["company"],
            "title": job["title"],
            "location": job["location"],
            "url": job["url"],
            "jd_excerpt": (job["jd_text"] or "")[:4000],
        })
        if len(tasks) >= limit:
            break
    return {
        "instructions": (
            "For each job, return an object {id, score (0-100 fit vs the candidate "
            "profile), reasons (2-4 short bullets), sector (aviation|rail|heavy|other), "
            "german_required (\"\"|A2|B1|B2|C1), visa_friendly_guess (bool), is_phd (bool), "
            "tier (A=top target|B|C)}. Weight: fuel-cell/H2 relevance, sector preference "
            "(aviation>rail>heavy), Stuttgart>Germany>Europe, job AND PhD equally. "
            "A2-B1 German only — flag (don't zero) roles needing B2+."
        ),
        "profile": profile,
        "jobs": tasks,
        "dropped_by_rules": dropped,
    }


def apply_scores(db: DB, scores: list[dict]) -> int:
    n = 0
    for s in scores:
        jid = s.get("id")
        if not jid or not db.get(jid):
            continue
        meta = {k: s.get(k) for k in
                ("reasons", "sector", "german_required", "visa_friendly_guess", "is_phd", "tier")}
        db.set_score(jid, int(s.get("score", 0)), meta)
        n += 1
    return n
