"""JobSpy source - the no-key volume backbone, and the reason it is often dark.

``python-jobspy`` scrapes several large boards directly and returns dated,
deduplicated postings with apply links.  It is a *library*, not a URL recipe, so
it has its own fetch path.

**Why this file was rewritten.**  It used to do this:

    except Exception as e:
        print(f"[jobspy] not installed ({e}); skipping")
        return []

Inside a scheduled run nobody reads stdout.  The configured *primary* discovery
source was therefore dead for weeks while every report and the dashboard showed
the run as healthy: an empty list and a quiet market look identical once the
print scrolls away.  Every exit from this module now writes a record into the run
ledger, so "JobSpy contributed nothing" always arrives with the reason attached.

**The measured constraint, so a buyer is not left guessing.**  python-jobspy
1.1.82 pins ``numpy==1.26.3``.  numpy 1.26.3 publishes no wheel for CPython 3.13;
pip falls back to a MinGW source build that *succeeds*, and the resulting numpy
segfaults on import.  So JobSpy coverage requires a Python 3.12 (or older)
environment.  ``pyproject.toml`` therefore declares the complete product
runtime as public CPython 3.12. On 3.13 the package is rejected instead of
pretending that the optional source is supported.
"""
from __future__ import annotations

import sys
from typing import Any

from ..models import RawPosting
from ..normalize import strip_html
from . import health as health_mod
from .registry import jobspy_sites

SOURCE = "jobspy"

PY313_NOTE = (
    "python-jobspy pins numpy==1.26.3, which publishes no wheel for CPython 3.13; "
    "the source build produces a numpy that faults on import. Run the pipeline on "
    "Python 3.12 to enable JobSpy coverage; Python 3.13 is outside the supported contract."
)


def import_diagnosis(exc: BaseException) -> str:
    """Why ``import jobspy`` failed, in terms the operator can act on."""
    base = f"{type(exc).__name__}: {exc}"
    if sys.version_info >= (3, 13):
        return f"{base}. {PY313_NOTE}"
    return f"{base}. Install it with `pip install 'job-automation[jobspy]'`."


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
    """JobSpy cells may be NaN/NaT/None - coerce to a clean string."""
    if v is None:
        return ""
    s = str(v)
    return "" if s.lower() in ("nan", "nat", "none") else s.strip()


def fetch_jobspy_with_health(cfg: dict[str, Any], max_age_days: int,
                             run: health_mod.SourceRun | None = None,
                             ) -> tuple[list[RawPosting], list[dict]]:
    """Run JobSpy and return (postings, records).

    `records` is never empty: even "disabled in the configuration" is recorded,
    because a report that omits a source entirely cannot be distinguished from a
    report about a source that found nothing.
    """
    ledger = run if run is not None else health_mod.active_run()
    records: list[dict] = []

    def _emit(**kwargs) -> None:
        if ledger is not None:
            records.append(ledger.record(SOURCE, **kwargs))
        else:
            records.append(health_mod.make_record(SOURCE, **kwargs))

    js = cfg.get("jobspy", {}) or {}
    if not js.get("enabled"):
        _emit(attempted=False, ok=False, jobs_yielded=0, status="disabled",
              error="jobspy.enabled is false in the profile configuration")
        return [], records

    try:
        from jobspy import scrape_jobs  # lazy: only needed when enabled
    except BaseException as exc:  # a broken numpy can raise beyond Exception
        _emit(attempted=True, ok=False, jobs_yielded=0, status="unavailable",
              error=import_diagnosis(exc))
        return [], records

    configured = js.get("sites")
    allowed, refused = jobspy_sites(configured, js.get("accept_tos_risk"))
    for site in refused:
        _emit(attempted=False, ok=False, jobs_yielded=0, status="opt_in_required",
              error=(f"{site} is configured but not listed in jobspy.accept_tos_risk; "
                     "its terms prohibit automated access, so it stays off."),
              site=site)
    if not allowed:
        _emit(attempted=False, ok=False, jobs_yielded=0, status="no_sites",
              error="no permitted jobspy sites remain after the opt-in filter")
        return [], records

    terms = [str(t) for t in js.get("search_terms", []) if str(t).strip()]
    if not terms:
        terms = [str(k) for k in cfg.get("include_keywords", []) if str(k).strip()][:4]
    locations = [str(l) for l in js.get("locations", []) if str(l).strip()]
    if not locations:
        profile_locations = cfg.get("search_locations", []) or []
        locations = [str(l) for l in profile_locations if str(l).strip()]
    if not locations:
        locations = [str(cfg.get("search_location", "") or "")]
    results_wanted = int(js.get("results_wanted", 40))
    country_indeed = js.get("country_indeed", "") or None
    hours_old = max(1, int(max_age_days) * 24)

    out: list[RawPosting] = []
    attempts = 0
    failures = 0
    last_error = ""
    for term in terms:
        for loc in locations:
            attempts += 1
            try:
                kwargs = dict(
                    site_name=allowed,
                    search_term=term,
                    google_search_term=f"{term} jobs near {loc} since last {max_age_days} days",
                    location=loc,
                    results_wanted=results_wanted,
                    hours_old=hours_old,
                    linkedin_fetch_description=True,
                    verbose=0,
                )
                if country_indeed:
                    kwargs["country_indeed"] = country_indeed
                df = scrape_jobs(**kwargs)
            except Exception as exc:
                failures += 1
                last_error = f"'{term}' @ '{loc}': {type(exc).__name__}: {exc}"
                continue
            for r in _records(df):
                url = _str(r.get("job_url_direct")) or _str(r.get("job_url"))
                if not url:
                    continue
                out.append(RawPosting(
                    source=f"{SOURCE}:{_str(r.get('site')) or 'web'}",
                    company=_str(r.get("company")) or "Unknown",
                    title=_str(r.get("title")),
                    location=_str(r.get("location")) or loc,
                    url=url,
                    jd_text=strip_html(_str(r.get("description"))),
                    posted_at=_str(r.get("date_posted")),
                    extra={"site": _str(r.get("site")), "search_term": term},
                ))

    if failures == attempts and attempts:
        _emit(attempted=True, ok=False, jobs_yielded=0, status="failed",
              error=f"all {attempts} JobSpy searches failed; last: {last_error}",
              sites=allowed)
    else:
        _emit(attempted=True, ok=bool(out), jobs_yielded=len(out),
              status="ok" if out else "empty",
              error="" if out else
                    f"{attempts} searches ran and returned no postings"
                    + (f"; {failures} of them errored, last: {last_error}" if failures else ""),
              sites=allowed, searches=attempts, search_failures=failures)
    return out, records


def fetch_jobspy(cfg: dict[str, Any], max_age_days: int) -> list[RawPosting]:
    """Backwards-compatible entry point.

    Still returns a plain list so existing callers do not change, but the outcome
    has already been written to the active run ledger by the time it returns, so
    an empty list here is never an unexplained zero in the report.
    """
    postings, _ = fetch_jobspy_with_health(cfg, max_age_days)
    return postings
