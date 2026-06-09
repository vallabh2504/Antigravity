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


def check(db: DB, states: tuple[str, ...] = ("scored", "approved", "docs_ready"),
          timeout: float = 12.0, reject_dead: bool = False) -> dict:
    jobs = [j for st in states for j in db.by_state(st)]
    results = []
    dead = 0
    with _client(timeout) as client:
        for j in jobs:
            url = j.get("url") or ""
            status, ok = "no-url", False
            if url:
                try:
                    r = client.head(url)
                    if r.status_code >= 400 or r.status_code == 405:
                        r = client.get(url)  # some servers reject HEAD
                    status, ok = str(r.status_code), (200 <= r.status_code < 400)
                except Exception as e:
                    status = f"ERR {type(e).__name__}"
            # persist link status into score_json
            sj = j.get("score_json") or {}
            sj["link_ok"] = ok
            sj["link_status"] = status
            db.set_score(j["id"], j.get("score") or 0, sj)
            if not ok:
                dead += 1
                if reject_dead:
                    db.set_state(j["id"], "rejected")
            results.append({"id": j["id"], "company": j["company"],
                            "status": status, "ok": ok, "url": url})
    return {"checked": len(results), "dead": dead, "results": results,
            "rejected_dead": reject_dead}
