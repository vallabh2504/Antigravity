"""Claude-side discovery backend — WebSearch only.

Why this exists: in a sandbox with an egress allowlist (no outbound HTTP to job
APIs, and WebFetch limited too), the agent's WebSearch tool is the ONLY channel
that reaches the open web. So the "claude" backend discovers jobs by emitting a
search PLAN, the agent runs each query with WebSearch, and the hits are ingested.

Fidelity vs the openclaw backend: WebSearch returns ~10 results/query with short
snippets (partial JD), not full structured API data. It's best-effort sampling —
good for "what's live right now"; OpenClaw's API/browser backend is for complete,
full-JD extraction at scale. Both feed the same normalize→score→report pipeline.
"""
from __future__ import annotations

from typing import Any


def build_search_plan(companies: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    kws = cfg.get("include_keywords", ["fuel cell", "hydrogen"])
    core = " OR ".join(f'"{k}"' for k in kws[:4]) if kws else "fuel cell"
    locs = cfg.get("locations", ["Germany"])
    primary_loc = "Stuttgart" if any("stuttgart" in l.lower() for l in locs) else "Germany"

    queries: list[dict[str, str]] = []

    # 1) Broad role searches (sector + geography), EN + DE
    broad = [
        f"fuel cell systems engineer jobs {primary_loc} 2026",
        f"hydrogen fuel cell engineer job Germany careers",
        f"Brennstoffzelle Systemingenieur Stellenangebote {primary_loc}",
        "hydrogen fuel cell PhD position Germany 2026",
        "fuel cell aviation jobs Europe hydrogen powertrain",
        "fuel cell heavy duty truck engineer job Germany",
        "fuel cell rail train hydrogen engineer job Europe",
    ]
    for q in broad:
        queries.append({"kind": "broad", "query": q})

    # 2) Per-company targeted searches (surfaces that company's live postings)
    for c in companies:
        if not c.get("enabled", True):
            continue
        name = c["name"]
        sect = " ".join(c.get("sectors", []))
        queries.append({"kind": "company", "company": name,
                        "query": f'{name} careers fuel cell hydrogen engineer job'})

    # 3) ATS dork searches (WebSearch honors site: operators)
    for host in ("boards.greenhouse.io", "jobs.lever.co", "jobs.ashbyhq.com",
                 "jobs.smartrecruiters.com"):
        queries.append({"kind": "ats", "query": f'site:{host} fuel cell hydrogen'})

    return {
        "instructions": (
            "Run each `query` with the WebSearch tool. For every relevant result, build a "
            "RawPosting-shaped object {company, title, location, url, jd_text (use the result "
            "snippet/summary), posted_at, source:'websearch'}. Keep only genuine job/PhD "
            "postings in fuel-cell/hydrogen for aviation/rail/heavy. Write them as a JSON list "
            "to search_results.json, then run: python -m jobauto ingest search_results.json"
        ),
        "queries": queries,
    }
