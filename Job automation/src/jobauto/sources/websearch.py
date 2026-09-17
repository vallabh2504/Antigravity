"""Agent-side discovery backend - a search PLAN the operator's own agent runs.

Why this exists: in a sandbox with an egress allowlist, an agent's web-search
tool is often the only channel that reaches the open web.  So this backend does
not fetch anything itself.  It emits the queries, the agent runs them with
whatever web tool it has, and the hits are fed back through ``ingest``.

Fidelity, stated so nobody mistakes this for the API path: a web search returns
roughly ten results per query with short snippets, not structured job data.  It
is best-effort sampling of "what is live right now"; the httpx backend is for
complete, full-description extraction at scale.  Both feed the same
normalize -> score -> report pipeline.

Every term in every query comes from the operator's profile.  This module knows
nothing about any industry, country or candidate, and it must stay that way: the
queries a jobseeker needs are the ones describing *their* search.
"""
from __future__ import annotations

from typing import Any

#: Search-operator hosts worth dorking, because a public board on one of them is
#: directly fetchable by an adapter in this package.
ATS_HOSTS = (
    "boards.greenhouse.io",
    "jobs.lever.co",
    "jobs.ashbyhq.com",
    "jobs.smartrecruiters.com",
    "jobs.personio.de",
)


def build_search_plan(companies: list[dict[str, Any]], cfg: dict[str, Any]) -> dict[str, Any]:
    """Queries for the agent to run, derived entirely from the profile."""
    keywords = [str(k).strip() for k in cfg.get("include_keywords", []) if str(k).strip()]
    roles = [str(r).strip() for r in cfg.get("target_roles", []) if str(r).strip()]
    locations = [str(l).strip() for l in cfg.get("search_locations", []) if str(l).strip()]
    if not locations:
        single = str(cfg.get("search_location", "") or "").strip()
        locations = [single] if single else []
    primary_location = locations[0] if locations else ""

    queries: list[dict[str, str]] = []
    terms = roles or keywords

    if not terms:
        return {
            "instructions": (
                "No search terms are configured. Add `target_roles` or "
                "`include_keywords` to your profile configuration; this stage "
                "deliberately invents nothing on your behalf."
            ),
            "queries": [],
            "warning": "empty search profile",
        }

    # 1) Role x location searches.
    for term in terms[:8]:
        for location in (locations or [""])[:3]:
            query = f"{term} jobs {location}".strip()
            queries.append({"kind": "broad", "query": query})

    # 2) Per-company targeted searches: surface that employer's live postings.
    for company in companies:
        if not company.get("enabled", True):
            continue
        name = company.get("name")
        if not name:
            continue
        focus = company.get("query") or (terms[0] if terms else "")
        queries.append({"kind": "company", "company": name,
                        "query": f"{name} careers {focus}".strip()})

    # 3) ATS dorks: a hit here is a board one of this package's adapters can fetch.
    for host in ATS_HOSTS:
        for term in terms[:2]:
            queries.append({"kind": "ats", "query": f'site:{host} "{term}"'})

    return {
        "instructions": (
            "Run each `query` with your web-search tool. For every relevant result build a "
            "RawPosting-shaped object {company, title, location, url, jd_text (use the result "
            "snippet or the fetched page), posted_at, source:'websearch'}. Keep only genuine "
            "job or research postings matching the profile above. Write them as a JSON list to "
            "search_results.json, then run: python -m jobauto ingest search_results.json"
        ),
        "profile_terms": terms,
        "profile_locations": locations,
        "primary_location": primary_location,
        "queries": queries,
    }
