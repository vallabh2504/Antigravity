"""Data models for the pipeline. Stdlib-only (dataclasses)."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

# Pipeline states (stage 7 tracking)
STATES = [
    "discovered",   # fetched + normalized
    "scored",       # LLM fit score attached
    "approved",     # human said yes (stage 4 gate)
    "rejected",     # human said no
    "docs_ready",   # tailored resume/cover drafted (stage 5)
    "prefilled",    # application form pre-filled, awaiting human submit (stage 6)
    "applied",      # human clicked send
    "screen",
    "onsite",
    "offer",
    "closed",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())


@dataclass
class RawPosting:
    """What a source adapter (or the agent) hands in, pre-normalization."""
    source: str                 # adapter name, e.g. "greenhouse:airbus"
    company: str
    title: str
    location: str = ""
    url: str = ""
    jd_text: str = ""           # FULL job description text (critical for tailoring)
    posted_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def content_id(self) -> str:
        key = "|".join(_norm(x) for x in (self.company, self.title, self.location, self.url))
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


@dataclass
class Score:
    value: int = 0              # 0-100 fit
    reasons: list[str] = field(default_factory=list)
    sector: str = ""            # aviation | rail | heavy | other
    german_required: str = ""   # "", "A2", "B1", "B2", "C1"...
    visa_friendly_guess: bool = True
    tier: str = ""              # A/B/C target tier
    is_phd: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Job:
    id: str
    source: str
    company: str
    title: str
    location: str
    url: str
    jd_text: str
    posted_at: str
    first_seen: str
    state: str = "discovered"
    score: int | None = None
    score_json: dict = field(default_factory=dict)
    scored_at: str = ""
    applied_at: str = ""
    updated_at: str = ""

    @classmethod
    def from_raw(cls, r: RawPosting) -> "Job":
        ts = now_iso()
        return cls(
            id=r.content_id(), source=r.source, company=r.company, title=r.title,
            location=r.location, url=r.url, jd_text=r.jd_text, posted_at=r.posted_at,
            first_seen=ts, updated_at=ts,
        )
