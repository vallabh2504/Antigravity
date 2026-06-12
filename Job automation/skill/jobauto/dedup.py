"""Cross-source dedup + persistent "new since last run" tracking.

The DB dedupes by content hash (company|title|location|url), so the SAME role coming from
two sources (different URLs) slips through as two rows. This collapses those by a fuzzy key
(normalised company + title, gender markers and punctuation stripped), preferring a direct
employer/ATS link over an aggregator link.

"New-only": the runner DB is ephemeral, so we keep a small committed seen-store
(dashboard/seen.json) mapping dedup-key -> first-seen date. Anything whose key is not in the
store is genuinely NEW this run; we tag it and record it.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

_GENDER = re.compile(
    r"\((?:m/w/d|w/m/d|m/f/d|f/m/d|w/m/x|m/w/x|x/m/w|d/m/w|d/w/m|m/w/divers|all genders|divers)\)", re.I)
_AGGREGATOR = ("linkedin.", "indeed.", "google.", "glassdoor.", "stepstone.", "xing.", "/jobs/view/")


def norm(s: str) -> str:
    s = _GENDER.sub(" ", s or "").lower()
    s = re.sub(r"[^a-z0-9äöüß ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def key(company: str, title: str) -> str:
    return f"{norm(company)}|{norm(title)}"


def _is_aggregator(url: str) -> bool:
    u = (url or "").lower()
    return any(a in u for a in _AGGREGATOR)


def collapse(raws: list) -> tuple[list, int]:
    """Collapse duplicate postings by fuzzy key; prefer a direct employer link. Returns
    (kept, dropped_count)."""
    by_key: dict[str, int] = {}
    out: list = []
    dropped = 0
    for r in raws:
        k = key(r.company, r.title)
        if k in by_key:
            idx = by_key[k]
            # upgrade to a direct (non-aggregator) link if the kept one is an aggregator
            if _is_aggregator(out[idx].url) and not _is_aggregator(r.url):
                out[idx] = r
            dropped += 1
            continue
        by_key[k] = len(out)
        out.append(r)
    return out, dropped


# --- persistent seen-store ---------------------------------------------------------------
def load_seen(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_seen(path: Path, seen: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(seen, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")


def mark_new(jobs: list[dict], seen: dict) -> tuple[set[str], dict]:
    """Given DB job dicts and the seen-store, return (new_keys, updated_seen). A job is NEW
    if its dedup key has never been recorded. Records today's date for new keys."""
    today = datetime.now(timezone.utc).date().isoformat()
    new_keys: set[str] = set()
    for j in jobs:
        k = key(j.get("company", ""), j.get("title", ""))
        if k not in seen:
            seen[k] = today
            new_keys.add(k)
    return new_keys, seen
