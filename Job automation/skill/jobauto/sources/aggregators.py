"""Aggregator sources — one query hits MANY employers across Europe at once, with a
POSTED DATE and a canonical APPLY LINK so we can filter to the last N days and trust
the link. This is the freshness backbone of discovery.

Source notes (freshness + link quality):
  * JSearch (Google for Jobs) — BEST for "last 3 days" across the whole market
        (LinkedIn/Indeed/company sites). `date_posted=3days`, returns job_apply_link +
        job_posted_at_datetime_utc. Needs a free RapidAPI key in secrets.yml.
  * Adzuna     — free app_id/app_key. `max_days_old` + `sort_by=date`, `created` date,
        stable redirect_url.
  * Bundesagentur — public key header. `veroeffentlichtseit` (published since N days),
        stable jobdetail URL via refnr.
  * Arbeitnow  — no auth; single feed with `created_at`; keyword-filtered client-side.
  * EURAXESS   — EU-wide research/PhD; HTML search, agent-parsed (no clean date API).
"""
from __future__ import annotations

from typing import Any

from ..models import RawPosting
from ..normalize import strip_html
from . import Recipe


def build_aggregator_recipes(cfg: dict[str, Any], secrets: dict[str, Any]) -> list[Recipe]:
    agg = cfg.get("aggregators", {})
    days = int(cfg.get("max_age_days", 3))
    out: list[Recipe] = []

    # --- JSearch (Google for Jobs) — primary freshness source -----------------
    j = agg.get("jsearch", {})
    if j.get("enabled"):
        key = secrets.get("rapidapi_key", "")
        q = j.get("query", "fuel cell hydrogen engineer").replace(" ", "%20")
        country = j.get("country", "de")
        dp = {1: "today", 3: "3days", 7: "week"}.get(days, "week")
        out.append(Recipe("JSearch", "agg_jsearch",
            f"https://jsearch.p.rapidapi.com/search?query={q}&date_posted={dp}"
            f"&page=1&num_pages=1&country={country}",
            headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}))

    # --- Adzuna (date-sorted, max age) ---------------------------------------
    a = agg.get("adzuna", {})
    if a.get("enabled"):
        ad = secrets.get("adzuna", {})
        country = a.get("country", "de")
        what = a.get("what", "fuel cell hydrogen").replace(" ", "%20")
        where = a.get("where", "").replace(" ", "%20")
        out.append(Recipe("Adzuna", "agg_adzuna",
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            f"?app_id={ad.get('app_id','')}&app_key={ad.get('app_key','')}"
            f"&what={what}&where={where}&results_per_page=50&max_days_old={days}"
            f"&sort_by=date&content-type=application/json"))

    if agg.get("arbeitnow", {}).get("enabled"):
        out.append(Recipe("Arbeitnow", "agg_arbeitnow",
                           "https://www.arbeitnow.com/api/job-board-api"))

    b = agg.get("bundesagentur", {})
    if b.get("enabled"):
        was = b.get("query", "Brennstoffzelle Wasserstoff").replace(" ", "%20")
        wo = b.get("where", "").replace(" ", "%20")
        out.append(Recipe("Bundesagentur", "agg_bundesagentur",
            f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/app/jobs"
            f"?was={was}&wo={wo}&veroeffentlichtseit={days}&page=1&size=50",
            headers={"X-API-Key": "jobboerse-jobsuche"}))

    e = agg.get("euraxess", {})
    if e.get("enabled"):
        kw = e.get("query", "fuel cell hydrogen").replace(" ", "+")
        out.append(Recipe("EURAXESS", "agg_euraxess",
            f"https://euraxess.ec.europa.eu/jobs/search?keywords={kw}", needs_detail=True))
    return out


def parse_aggregator(recipe: Recipe, payload: Any, include_kw: list[str]) -> list[RawPosting]:
    p = recipe.portal
    out: list[RawPosting] = []
    kw = [k.lower() for k in include_kw]

    def _match(text: str) -> bool:
        return not kw or any(k in text.lower() for k in kw)

    try:
        if p == "agg_jsearch":
            for j in payload.get("data", []):
                loc = ", ".join(filter(None, [j.get("job_city"), j.get("job_country")]))
                out.append(RawPosting(p, j.get("employer_name", "JSearch"), j.get("job_title", ""),
                    loc, j.get("job_apply_link", ""), strip_html(j.get("job_description", "")),
                    str(j.get("job_posted_at_datetime_utc", ""))))
        elif p == "agg_adzuna":
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
                    "", str(j.get("aktuelleVeroeffentlichungsdatum", j.get("eintrittsdatum", ""))),
                    {"refnr": ref, "needs_detail": True}))
    except (AttributeError, TypeError):
        pass
    return out
