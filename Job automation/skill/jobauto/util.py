"""Small shared utilities (date parsing for freshness)."""
from __future__ import annotations

from datetime import datetime, timezone, date
import re


def parse_date(s: str) -> date | None:
    """Best-effort parse of heterogeneous posted_at strings -> date (UTC)."""
    if not s:
        return None
    s = s.strip()
    # ISO / RFC3339 (Greenhouse, Lever, JSearch, Adzuna 'created')
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    # common formats
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s[:len(fmt) + 4], fmt).date()
        except ValueError:
            continue
    # epoch seconds/millis
    m = re.fullmatch(r"\d{10,13}", s)
    if m:
        v = int(s)
        if v > 1e12:
            v //= 1000
        return datetime.fromtimestamp(v, tz=timezone.utc).date()
    return None


def age_days(s: str) -> int | None:
    d = parse_date(s)
    if not d:
        return None
    return (datetime.now(timezone.utc).date() - d).days
