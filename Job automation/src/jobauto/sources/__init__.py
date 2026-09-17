"""Stage 1 discovery: portal recipes + parsers.

Two execution backends share these recipes:
  * httpx backend  -> jobauto.sources.fetch (for a host with outbound access)
  * agent backend  -> `cli manifest` emits the URLs; an external agent fetches
                      them with its web/browser tools and feeds raw JSON back via
                      `cli ingest`.

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


def build_recipes(companies: list[dict[str, Any]],
                  cfg: dict[str, Any] | None = None) -> list[Recipe]:
    """Turn watchlist entries into fetchable requests.

    `cfg` supplies profile-level defaults (today: the market to narrow boards to).
    It is optional so existing callers keep working, and every value it provides
    comes from the operator's own configuration rather than from this module.
    """
    if cfg is None:
        # Keep direct callers useful while still deriving board geography from
        # the operator's profile. A source module must not invent a country,
        # but an existing profile is an explicit preference.
        try:
            from .. import config as config_module
            settings = config_module.load_config() or {}
        except Exception:
            settings = {}
    else:
        settings = cfg
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
            # Server-side keyword filter via `q` so we get the profile's roles rather
            # than every posting on the board; `country` narrows it to the target market.
            q = c.get("query", "").replace(" ", "%20")
            qparam = f"&q={q}" if q else ""
            configured_countries = settings.get("target_countries")
            if isinstance(configured_countries, (list, tuple)):
                configured_countries = configured_countries[0] if configured_countries else ""
            market = str(c.get("country") or settings.get("search_country")
                         or configured_countries or "").strip()
            cparam = f"&country={market}" if market else ""
            out.append(Recipe(name, portal,
                f"https://api.smartrecruiters.com/v1/companies/{tok}/postings?limit=100{cparam}{qparam}",
                sectors=sectors, needs_detail=True,
                detail_url_tmpl="https://api.smartrecruiters.com/v1/companies/" + tok + "/postings/{id}"))
        elif portal == "workday":
            from .workday import parse_workday_token
            host, tenant, board = parse_workday_token(tok)
            query = c.get("query", "")
            out.append(Recipe(name, portal,
                f"https://{host}/wday/cxs/{tenant}/{board}/jobs",
                method="POST",
                body={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": query},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                sectors=sectors, needs_detail=True,
                detail_url_tmpl=f"https://{host}/wday/cxs/{tenant}/{board}{{path}}"))
        elif portal == "personio":
            out.append(Recipe(name, portal,
                f"https://{tok}.jobs.personio.de/xml", sectors=sectors))
        else:  # custom portal (DLR, BMW careers, etc.) — agent fetches the search page
            out.append(Recipe(name, "custom", c.get("careers_url", ""), sectors=sectors,
                              needs_detail=True))
    return out


def parse(recipe: Recipe, payload: Any) -> list[RawPosting]:
    """Map a list-endpoint payload to RawPostings. `payload` is parsed JSON or XML text."""
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
            from .workday import parse_workday
            return parse_workday(recipe, payload)
        elif p == "personio":
            from .personio import parse_personio
            if isinstance(payload, str):
                return parse_personio(recipe, payload)
            return []
    except (AttributeError, TypeError):
        pass
    return out
