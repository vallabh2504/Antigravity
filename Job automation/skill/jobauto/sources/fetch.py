"""httpx execution backend (OpenClaw / any host with outbound access).

In this dev container outbound HTTP to job APIs is blocked, so the agent backend
(`cli manifest` + web tools + `cli ingest`) is used instead. This module is what
OpenClaw will use once the skill runs on the user's machine.
"""
from __future__ import annotations

import json
from typing import Any

from ..models import RawPosting
from . import Recipe, parse


def _client():
    import httpx  # lazy: only needed on the httpx backend
    # follow_redirects: many careers pages 301/302/308 to a trailing-slash variant; without
    # this every one of them fails. Browser-like UA: some hosts 403 a bare client.
    return httpx.Client(timeout=20, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"})


def fetch_recipe(recipe: Recipe) -> list[RawPosting]:
    with _client() as client:
        if recipe.method == "POST":
            resp = client.post(recipe.list_url, json=recipe.body or {}, headers=recipe.headers)
        else:
            resp = client.get(recipe.list_url, headers=recipe.headers)
        resp.raise_for_status()
        payload: Any = resp.json()
        postings = parse(recipe, payload)
        # follow detail fetches for full JD where required
        if recipe.needs_detail and recipe.detail_url_tmpl:
            for p in postings:
                try:
                    if recipe.portal == "smartrecruiters" and p.extra.get("id"):
                        d = client.get(recipe.detail_url_tmpl.format(id=p.extra["id"])).json()
                        p.jd_text = _smartrecruiters_jd(d)
                        p.url = d.get("applyUrl") or p.url
                except Exception:
                    continue
        return postings


def _smartrecruiters_jd(detail: dict) -> str:
    from ..normalize import strip_html
    secs = (detail.get("jobAd") or {}).get("sections") or {}
    parts = [strip_html((secs.get(k) or {}).get("text", "")) for k in
             ("companyDescription", "jobDescription", "qualifications", "additionalInformation")]
    return "\n\n".join(p for p in parts if p)


def fetch_all(recipes: list[Recipe]) -> list[RawPosting]:
    out: list[RawPosting] = []
    for r in recipes:
        try:
            out.extend(fetch_recipe(r))
        except Exception as e:  # one bad source shouldn't kill the run
            print(f"[fetch] {r.company} ({r.portal}) failed: {e}")
    return out


def manifest(recipes: list[Recipe]) -> list[dict]:
    """For the agent backend: the exact requests to make per company."""
    return [
        {"company": r.company, "portal": r.portal, "method": r.method,
         "url": r.list_url, "body": r.body, "needs_detail": r.needs_detail,
         "detail_url_tmpl": r.detail_url_tmpl, "sectors": r.sectors}
        for r in recipes
    ]
