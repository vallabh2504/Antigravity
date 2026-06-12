"""Validate that each posting's apply URL is actually live (not 404/expired).

This is the antidote to the dead/expired links problem: after discovery, before
showing jobs, HEAD/GET each apply URL and flag/drop the dead ones. Needs real network
(run on OpenClaw / your machine; a locked-down sandbox will mark everything unreachable).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from .db import DB
from .util import parse_date


def _client(timeout: float):
    import httpx
    return httpx.Client(timeout=timeout, follow_redirects=True,
                        headers={"User-Agent": "Mozilla/5.0 jobauto-linkcheck"})


# Status codes that mean the posting is genuinely GONE (safe to auto-reject).
_GONE = {404, 410}
# Anti-bot / auth walls from a datacenter IP (LinkedIn 999, Indeed/Glassdoor 403, rate
# limits). The job is almost certainly live in a browser, so we KEEP it and just flag it
# "unverified" rather than falsely calling it dead.
_BLOCKED = {401, 403, 429, 999}

# Phrases that mean a 200-OK page is actually a CLOSED/expired posting (common on LinkedIn,
# Indeed and ATS pages that return 200 even after the role is filled).
_EXPIRED_MARKERS = (
    "no longer accepting applications", "no longer available", "this job is no longer",
    "position has been filled", "posting has expired", "job has expired", "applications are closed",
    "nicht mehr verfügbar", "stellenanzeige ist nicht mehr", "anzeige nicht mehr",
    "diese stelle ist nicht mehr", "bewerbungsfrist ist abgelaufen", "stelle wurde besetzt",
)

# --- REAL posting-date verification ------------------------------------------------------
# Aggregators (LinkedIn/Indeed/Google) report when THEY re-indexed a job, not when it was
# actually posted, so a 3-month-old role can show as "3 days ago". The only reliable date is
# on the posting's own page. We read it and re-filter on the TRUTH.
_JSONLD_DATE = re.compile(r'"dateposted"\s*:\s*"([^"]{6,40})"', re.I)            # Google JobPosting schema
_META_DATE = re.compile(r'(?:article:published_time|og:updated_time)["\']\s*content=["\']([^"\']+)', re.I)
_DMY = re.compile(r'\b(\d{2})\.(\d{2})\.(\d{4})\b')                              # 18.03.2026
_YMD = re.compile(r'\b(\d{4})-(\d{2})-(\d{2})\b')                                # 2026-03-18


def extract_post_date(text: str) -> date | None:
    """Best authoritative posting date from a job page: JSON-LD datePosted, then a
    published-time meta tag, then the most-recent PAST full date visible on the page."""
    if not text:
        return None
    m = _JSONLD_DATE.search(text)
    if m:
        d = parse_date(m.group(1))
        if d:
            return d
    m = _META_DATE.search(text)
    if m:
        d = parse_date(m.group(1))
        if d:
            return d
    today = datetime.now(timezone.utc).date()
    cands: list[date] = []
    for mm in _DMY.finditer(text):
        try:
            cands.append(date(int(mm.group(3)), int(mm.group(2)), int(mm.group(1))))
        except ValueError:
            pass
    for mm in _YMD.finditer(text):
        try:
            cands.append(date(int(mm.group(1)), int(mm.group(2)), int(mm.group(3))))
        except ValueError:
            pass
    past = [c for c in cands if c <= today]   # a posting date is in the past; ignore future start/deadline dates
    return max(past) if past else None


def check(db: DB, states: tuple[str, ...] = ("discovered", "scored", "approved", "docs_ready"),
          timeout: float = 12.0, reject_dead: bool = False,
          max_age_days: int | None = None) -> dict:
    jobs = [j for st in states for j in db.by_state(st)]
    results = []
    dead = blocked = stale = 0
    today = datetime.now(timezone.utc).date()
    with _client(timeout) as client:
        for j in jobs:
            url = j.get("url") or ""
            code: int | None = None
            expired_body = False
            real_date: date | None = None
            status, link_state = "no-url", "no-url"
            if url:
                try:
                    # GET (not HEAD) so we can read the body for closed/expired markers AND
                    # the REAL posting date (the aggregator's "freshness" is not trustworthy).
                    r = client.get(url)
                    code = r.status_code
                    status = str(code)
                    if 200 <= code < 400:
                        text = r.text or ""
                        expired_body = any(m in text.lower() for m in _EXPIRED_MARKERS)
                        real_date = extract_post_date(text)
                except Exception as e:
                    status = f"ERR {type(e).__name__}"
            # real-date freshness: if the page's own date is older than the window, it is stale
            # no matter what the aggregator claimed (this is the BMW "18.03" case).
            real_age = (today - real_date).days if real_date else None
            too_old = (max_age_days is not None and real_age is not None and real_age > max_age_days)
            # classify
            if expired_body:
                link_state = "gone"; status += " expired"
            elif too_old:
                link_state = "gone"; status += f" stale({real_date})"
            elif code is not None and 200 <= code < 400:
                link_state = "live"
            elif code in _GONE:
                link_state = "gone"
            elif code in _BLOCKED:
                link_state = "unverified"
            elif url:
                link_state = "unverified"   # network error / odd code: don't call it dead
            # persist
            sj = j.get("score_json") or {}
            sj["link_ok"] = (link_state == "live")
            sj["link_state"] = link_state
            sj["link_status"] = status
            if real_date:
                sj["posting_date"] = real_date.isoformat()
                sj["verified_age_days"] = real_age
                db.set_posted_at(j["id"], real_date.isoformat())  # dashboard age = TRUE age
            sj["date_verified"] = real_date is not None
            db.set_score(j["id"], j.get("score") or 0, sj)
            if link_state == "gone":
                dead += 1
                if too_old and not expired_body:
                    stale += 1
                if reject_dead:
                    db.set_state(j["id"], "rejected")
            elif link_state == "unverified":
                blocked += 1
            results.append({"id": j["id"], "company": j["company"], "status": status,
                            "link_state": link_state, "url": url,
                            "posting_date": real_date.isoformat() if real_date else None})
    return {"checked": len(results), "dead": dead, "blocked": blocked, "stale": stale,
            "results": results, "rejected_dead": reject_dead}
