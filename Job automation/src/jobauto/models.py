"""Data models for the pipeline. Stdlib-only (dataclasses)."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

# Pipeline states (stage 7 tracking)
STATES = [
    "discovered",   # fetched + normalized
    "scored",       # LLM fit score attached
    "approved",     # human said yes (stage 4 gate)
    "rejected",     # human said no
    "docs_review",  # tailored documents rendered; truth/visual review pending
    "docs_ready",   # tailored documents passed content, PDF, ATS, and visual review
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


def canonical_company(value: str | None) -> str:
    text = re.sub(r"[^\w\s-]", " ", _norm(value))
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+(?:gmbh|ag|se|inc|ltd|limited|llc|kg|mbh)$", "", text).strip()


def canonical_location(value: str | None) -> str:
    text = re.sub(r"[^\w\s-]", " ", _norm(value))
    tokens = [t for t in text.split() if t not in
              {"germany", "deutschland", "de", "remote", "hybrid"}]
    return " ".join(tokens)


def canonical_title(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s+#-]", " ", _norm(value))).strip()


_TRACKING_QUERY_KEYS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "ref", "referrer", "source",
    "trk", "trackingid", "campaign", "campaignid",
}


def canonicalize_url(url: str | None) -> str:
    """Return a stable job URL while retaining query keys that identify a job."""
    value = (url or "").strip()
    if not value:
        return ""
    try:
        parts = urlsplit(value)
        if not parts.netloc:
            return value.rstrip("/")
        host = parts.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        path = re.sub(r"/{2,}", "/", parts.path).rstrip("/") or "/"
        query = []
        for key, val in parse_qsl(parts.query, keep_blank_values=True):
            lowered = key.lower()
            if lowered.startswith("utm_") or lowered in _TRACKING_QUERY_KEYS:
                continue
            query.append((key, val))
        return urlunsplit(((parts.scheme or "https").lower(), host, path,
                           urlencode(sorted(query)), ""))
    except (TypeError, ValueError):
        return value.rstrip("/")


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
        # If the URL contains a unique vacancy identifier (e.g. LinkedIn /jobs/view/12345,
        # SmartRecruiters ID, Workday path, DLR job nr), use canonical URL as the primary key.
        canon_url = canonicalize_url(self.url)
        if re.search(r"/(?:jobs/view|job|posting|stellenangebote)/\w+", canon_url, re.I):
            return hashlib.sha1(canon_url.encode("utf-8")).hexdigest()[:16]
        # Career sites frequently use opaque paths such as `/openings/a7f...`
        # that do not match the short list above. Include the normalized URL
        # path/query and the source/content tuple so distinct vacancies cannot
        # collapse merely because their employer and title match.
        parts = urlsplit(canon_url)
        url_identity = urlunsplit((parts.scheme, parts.netloc, parts.path,
                                   urlencode(sorted(parse_qsl(parts.query,
                                                               keep_blank_values=True))), ""))
        identity = (self.source, canonical_company(self.company),
                    canonical_title(self.title), canonical_location(self.location),
                    _norm(self.posted_at), url_identity)
        key = "|".join(identity) if any(identity) else canon_url
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


@dataclass
class Score:
    value: int = 0              # 0-100 fit
    reasons: list[str] = field(default_factory=list)
    sector: str = ""            # aviation | rail | heavy | other
    german_required: str = ""   # "", "A2", "B1", "B2", "C1"...
    visa_friendly_guess: bool = False
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
            location=r.location, url=canonicalize_url(r.url), jd_text=r.jd_text, posted_at=r.posted_at,
            first_seen=ts, updated_at=ts,
        )
