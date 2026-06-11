"""JobSpy source — the open-source replacement for the paid JSearch/RapidAPI route.

`python-jobspy` scrapes LinkedIn, Indeed, Google for Jobs and Glassdoor DIRECTLY
(no API key, no signup), returning a dated, deduped set of postings with apply
links. This is the freshness/volume backbone now that we've dropped RapidAPI.

It is a *library*, not a URL recipe, so it has its own fetch path (called from
cmd_fetch alongside the httpx recipe backend). Each (search term x location) is a
separate scrape; one bad scrape never kills the run.

Reliability note: scrapers can be rate-limited or IP-blocked on datacenter hosts
(GitHub runners occasionally get a 429 from LinkedIn/Indeed). That's why the free
official APIs (Bundesagentur/Arbeitnow) stay on as a never-blocked backbone.
"""
from __future__ import annotations

from typing import Any

from ..models import RawPosting
from ..normalize import strip_html


def _records(df: Any) -> list[dict]:
    """DataFrame -> list of plain dicts, tolerant of JobSpy returning None/empty."""
    if df is None:
        return []
    try:
        if getattr(df, "empty", True):
            return []
        return df.to_dict("records")
    except Exception:
        return []


def _str(v: Any) -> str:
    """JobSpy cells may be NaN/NaT/None — coerce to a clean string."""
    if v is None:
        return ""
    s = str(v)
    return "" if s.lower() in ("nan", "nat", "none") else s.strip()


def fetch_jobspy(cfg: dict[str, Any], max_age_days: int) -> list[RawPosting]:
    js = cfg.get("jobspy", {})
    if not js.get("enabled"):
        return []
    try:
        from jobspy import scrape_jobs  # lazy: only needed when enabled
    except Exception as e:
        print(f"[jobspy] not installed ({e}); skipping. `pip install python-jobspy`")
        return []

    sites = js.get("sites", ["indeed", "linkedin", "google"])
    terms = js.get("search_terms", ["fuel cell engineer", "hydrogen engineer"])
    locations = js.get("locations", ["Germany"])
    results_wanted = int(js.get("results_wanted", 40))
    country_indeed = js.get("country_indeed", "Germany")
    hours_old = max(1, int(max_age_days) * 24)

    out: list[RawPosting] = []
    for term in terms:
        for loc in locations:
            try:
                df = scrape_jobs(
                    site_name=sites,
                    search_term=term,
                    google_search_term=f"{term} jobs near {loc} since last {max_age_days} days",
                    location=loc,
                    results_wanted=results_wanted,
                    hours_old=hours_old,
                    country_indeed=country_indeed,
                    linkedin_fetch_description=True,  # pull JD text for scoring/tailoring
                    verbose=0,
                )
            except Exception as e:
                print(f"[jobspy] '{term}' @ '{loc}' failed: {e}")
                continue
            recs = _records(df)
            print(f"[jobspy] '{term}' @ '{loc}': {len(recs)} rows")
            for r in recs:
                url = _str(r.get("job_url_direct")) or _str(r.get("job_url"))
                if not url:
                    continue
                out.append(RawPosting(
                    source=f"jobspy:{_str(r.get('site')) or 'web'}",
                    company=_str(r.get("company")) or "Unknown",
                    title=_str(r.get("title")),
                    location=_str(r.get("location")) or loc,
                    url=url,
                    jd_text=strip_html(_str(r.get("description"))),
                    posted_at=_str(r.get("date_posted")),
                    extra={"site": _str(r.get("site")), "search_term": term},
                ))
    return out
