"""Stage 1 discovery: portal recipes + parsers.

Two execution backends share these recipes:
  * httpx backend  -> jobauto.sources.fetch (used by OpenClaw / any unblocked host)
  * agent backend  -> `cli manifest` emits the URLs; the agent (Claude/OpenClaw)
                      fetches them with its web/browser tools and feeds raw JSON
                      back via `cli ingest`.

A "recipe" tells the caller exactly which HTTP request(s) to make for a company,
and `parse()` turns the response payload into RawPosting objects (with FULL JD
text where the list endpoint already includes it; otherwise a detail fetch is
flagged via `needs_detail`).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..models import RawPosting
from ..normalize import strip_html


@dataclass
class Recipe:
    company: str
    portal: str
    list_url: str
    method: str = "GET"
    body: dict | None = None
    headers: dict = field(default_factory=dict)
    sectors: list[str] = field(default_factory=list)
    # if the list endpoint lacks JD text, detail_url_tmpl.format(id=...) fetches it
    needs_detail: bool = False
    detail_url_tmpl: str = ""


def build_recipes(companies: list[dict[str, Any]]) -> list[Recipe]:
    out: list[Recipe] = []
    for c in companies:
        if not c.get("enabled", True):
            continue
        portal = c.get("portal", "custom")
        tok = c.get("token", "")
        name = c["name"]
        sectors = c.get("sectors", [])
        if portal == "greenhouse":
            out.append(Recipe(name, portal,
                f"https://boards-api.greenhouse.io/v1/boards/{tok}/jobs?content=true",
                sectors=sectors))
        elif portal == "lever":
            out.append(Recipe(name, portal,
                f"https://api.lever.co/v0/postings/{tok}?mode=json", sectors=sectors))
        elif portal == "ashby":
            out.append(Recipe(name, portal,
                f"https://api.ashbyhq.com/posting-api/job-board/{tok}?includeCompensation=true",
                sectors=sectors))
        elif portal == "smartrecruiters":
            # Bosch et al. List has no full JD -> detail fetch per posting.
            # Server-side keyword filter via `q` so we get fuel-cell roles, not all 100 postings.
            q = c.get("query", "").replace(" ", "%20")
            qparam = f"&q={q}" if q else ""
            out.append(Recipe(name, portal,
                f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?limit=100{qparam}",
                sectors=sectors, needs_detail=True,
                detail_url_tmpl="https://api.smartrecruiters.com/v1/companies/" + tok + "/postings/{id}"))
        elif portal == "workday":
            # tok = "tenant|site|host"  e.g. "siemens|siemens|jobs.siemens.com"
            tenant, site, host = (tok.split("|") + ["", ""])[:3]
            out.append(Recipe(name, portal,
                f"https://{host}/wday/cxs/{tenant}/{site}/jobs",
                method="POST", body={"limit": 50, "offset": 0, "searchText": c.get("query", "")},
                headers={"Content-Type": "application/json"},
                sectors=sectors, needs_detail=True,
                detail_url_tmpl=f"https://{host}/wday/cxs/{tenant}/{site}{{path}}"))
        else:  # custom portal (DLR, BMW careers, etc.) — agent fetches the search page
            out.append(Recipe(name, "custom", c.get("careers_url", ""), sectors=sectors,
                              needs_detail=True))
    return out


def parse(recipe: Recipe, payload: Any) -> list[RawPosting]:
    """Map a list-endpoint payload to RawPostings. `payload` is parsed JSON."""
    p = recipe.portal
    src = f"{p}:{recipe.company}"
    out: list[RawPosting] = []
    try:
        if p == "greenhouse":
            for j in payload.get("jobs", []):
                out.append(RawPosting(src, recipe.company, j.get("title", ""),
                    (j.get("location") or {}).get("name", ""), j.get("absolute_url", ""),
                    strip_html(j.get("content", "")), str(j.get("updated_at", "")),
                    {"sectors": recipe.sectors}))
        elif p == "lever":
            for j in payload:
                out.append(RawPosting(src, recipe.company, j.get("text", ""),
                    (j.get("categories") or {}).get("location", ""), j.get("hostedUrl", ""),
                    j.get("descriptionPlain") or strip_html(j.get("description", "")),
                    str(j.get("createdAt", "")), {"sectors": recipe.sectors}))
        elif p == "ashby":
            for j in payload.get("jobs", []):
                out.append(RawPosting(src, recipe.company, j.get("title", ""),
                    j.get("location", ""), j.get("jobUrl", ""),
                    strip_html(j.get("descriptionHtml", "")), "", {"sectors": recipe.sectors}))
        elif p == "smartrecruiters":
            for j in payload.get("content", []):
                loc = j.get("location") or {}
                out.append(RawPosting(src, recipe.company, j.get("name", ""),
                    ", ".join(filter(None, [loc.get("city"), loc.get("country")])),
                    f"https://jobs.smartrecruiters.com/{recipe.company}/{j.get('id')}",
                    "",  # JD comes from detail fetch
                    str(j.get("releasedDate", "")),
                    {"sectors": recipe.sectors, "id": j.get("id"), "needs_detail": True}))
        elif p == "workday":
            for j in payload.get("jobPostings", []):
                out.append(RawPosting(src, recipe.company, j.get("title", ""),
                    j.get("locationsText", ""), "", "",
                    j.get("postedOn", ""),
                    {"sectors": recipe.sectors, "path": j.get("externalPath"), "needs_detail": True}))
    except (AttributeError, TypeError):
        pass
    return out
