"""Validate that each posting's apply URL is actually live (not 404/expired).

This is the antidote to the dead/expired links problem: after discovery, before
showing jobs, HEAD/GET each apply URL and flag/drop the dead ones. Needs real network
(run on OpenClaw / your machine; a locked-down sandbox will mark everything unreachable).
"""
from __future__ import annotations

import json
from .db import DB


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


def check(db: DB, states: tuple[str, ...] = ("discovered", "scored", "approved", "docs_ready"),
          timeout: float = 12.0, reject_dead: bool = False) -> dict:
    jobs = [j for st in states for j in db.by_state(st)]
    results = []
    dead = blocked = 0
    with _client(timeout) as client:
        for j in jobs:
            url = j.get("url") or ""
            code: int | None = None
            expired_body = False
            status, link_state = "no-url", "no-url"
            if url:
                try:
                    # GET (not HEAD) so we can inspect the body for "closed/expired" markers;
                    # HEAD never reveals an expired-but-200 posting.
                    r = client.get(url)
                    code = r.status_code
                    status = str(code)
                    if 200 <= code < 400:
                        body = (r.text or "").lower()
                        expired_body = any(m in body for m in _EXPIRED_MARKERS)
                except Exception as e:
                    status = f"ERR {type(e).__name__}"
            # classify: live / gone / unverified(blocked)
            if expired_body:
                link_state = "gone"; status += " expired"
            elif code is not None and 200 <= code < 400:
                link_state = "live"
            elif code in _GONE:
                link_state = "gone"
            elif code in _BLOCKED:
                link_state = "unverified"
            elif url:
                link_state = "unverified"   # network error / odd code: don't call it dead
            # persist link status into score_json
            sj = j.get("score_json") or {}
            sj["link_ok"] = (link_state == "live")
            sj["link_state"] = link_state
            sj["link_status"] = status
            db.set_score(j["id"], j.get("score") or 0, sj)
            if link_state == "gone":
                dead += 1
                if reject_dead:
                    db.set_state(j["id"], "rejected")
            elif link_state == "unverified":
                blocked += 1
            results.append({"id": j["id"], "company": j["company"],
                            "status": status, "link_state": link_state, "url": url})
    return {"checked": len(results), "dead": dead, "blocked": blocked,
            "results": results, "rejected_dead": reject_dead}
