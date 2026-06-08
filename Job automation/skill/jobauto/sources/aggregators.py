"""Aggregator sources — one query hits MANY employers across Europe at once.

This is how we get breadth without hand-listing companies. Each function returns
either a Recipe (for the httpx/agent backends) or parses a payload into RawPostings.

Auth notes:
  * Adzuna       — free app_id/app_key (register at developer.adzuna.com). Put in secrets.yml.
  * Arbeitnow    — no auth, Germany-heavy. Filter keywords client-side.
  * Bundesagentur— public API key header (the well-known "jobboerse-jobsuche" client id).
  * EURAXESS     — EU-wide research/PhD jobs; HTML search, agent-parsed.
All are programmatic-access friendly; we stay gentle (one query, paginated).
"""
from __future__ import annotations

from typing import Any

from ..models import RawPosting
from ..normalize import strip_html
from . import Recipe


def build_aggregator_recipes(cfg: dict[str, Any], secrets: dict[str, Any]) -> list[Recipe]:
    agg = cfg.get("aggregators", {})
    out: list[Recipe] = []

    a = agg.get("adzuna", {})
    if a.get("enabled"):
        ad = secrets.get("adzuna", {})
        country = a.get("country", "de")
        what = a.get("what", "fuel cell hydrogen").replace(" ", "%20")
        where = a.get("where", "").replace(" ", "%20")
        url = (f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
               f"?app_id={ad.get('app_id','')}&app_key={ad.get('app_key','')}"
               f"&what={what}&where={where}&results_per_page=50&content-type=application/json")
        out.append(Recipe("Adzuna", "agg_adzuna", url))

    if agg.get("arbeitnow", {}).get("enabled"):
        out.append(Recipe("Arbeitnow", "agg_arbeitnow",
                           "https://www.arbeitnow.com/api/job-board-api"))

    b = agg.get("bundesagentur", {})
    if b.get("enabled"):
        was = b.get("query", "Brennstoffzelle Wasserstoff").replace(" ", "%20")
        wo = b.get("where", "").replace(" ", "%20")
        out.append(Recipe("Bundesagentur", "agg_bundesagentur",
            f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs"
            f"?was={was}&wo={wo}&page=1&size=50",
            headers={"X-API-Key": "jobboerse-jobsuche"}))

    e = agg.get("euraxess", {})
    if e.get("enabled"):
        kw = e.get("query", "fuel cell hydrogen").replace(" ", "+")
        out.append(Recipe("EURAXESS", "agg_euraxess",
            f"https://euraxess.ec.europa.eu/jobs/search?keywords={kw}",
            needs_detail=True))  # HTML -> agent parses listing + detail
    return out


def parse_aggregator(recipe: Recipe, payload: Any, include_kw: list[str]) -> list[RawPosting]:
    p = recipe.portal
    out: list[RawPosting] = []
    kw = [k.lower() for k in include_kw]

    def _match(text: str) -> bool:
        return not kw or any(k in text.lower() for k in kw)

    try:
        if p == "agg_adzuna":
            for j in payload.get("results", []):
                out.append(RawPosting(p, (j.get("company") or {}).get("display_name", "Adzuna"),
                    j.get("title", ""), (j.get("location") or {}).get("display_name", ""),
                    j.get("redirect_url", ""), strip_html(j.get("description", "")),
                    str(j.get("created", ""))))
        elif p == "agg_arbeitnow":
            for j in payload.get("data", []):
                blob = f"{j.get('title','')} {' '.join(j.get('tags',[]))} {j.get('description','')}"
                if not _match(blob):
                    continue
                out.append(RawPosting(p, j.get("company_name", "Arbeitnow"), j.get("title", ""),
                    j.get("location", ""), j.get("url", ""),
                    strip_html(j.get("description", "")), str(j.get("created_at", ""))))
        elif p == "agg_bundesagentur":
            for j in payload.get("stellenangebote", []):
                ref = j.get("refnr", "")
                out.append(RawPosting(p, j.get("arbeitgeber", "Bundesagentur"), j.get("titel", ""),
                    (j.get("arbeitsort") or {}).get("ort", ""),
                    f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}",
                    "", str(j.get("eintrittsdatum", "")), {"refnr": ref, "needs_detail": True}))
    except (AttributeError, TypeError):
        pass
    return out
