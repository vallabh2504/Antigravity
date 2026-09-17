"""SQLite pipeline store (stage 7). Stdlib sqlite3 only."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import (STATES, Job, canonical_company, canonical_location, canonical_title,
                     canonicalize_url, now_iso)


LEGAL_TRANSITIONS = {
    "discovered": {"scored", "approved", "rejected", "closed"},
    "scored": {"approved", "rejected", "closed"},
    "approved": {"docs_review", "rejected", "closed"},
    "docs_review": {"docs_ready", "approved", "rejected", "closed"},
    "docs_ready": {"prefilled", "applied", "rejected", "closed"},
    "prefilled": {"applied", "rejected", "closed"},
    "applied": {"screen", "closed"},
    "screen": {"onsite", "offer", "closed"},
    "onsite": {"offer", "closed"},
    "offer": {"closed"},
    "rejected": set(),
    "closed": set(),
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    source      TEXT,
    company     TEXT,
    title       TEXT,
    location    TEXT,
    url         TEXT,
    jd_text     TEXT,
    posted_at   TEXT,
    first_seen  TEXT,
    state       TEXT DEFAULT 'discovered',
    score       INTEGER,
    score_json  TEXT DEFAULT '{}',
    scored_at   TEXT DEFAULT '',
    applied_at  TEXT DEFAULT '',
    updated_at  TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score);
"""


class DB:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # ---- writes -------------------------------------------------------
    def upsert(self, job: Job) -> bool:
        """Insert or enrich a posting, preserving workflow state and first_seen."""
        job.url = canonicalize_url(job.url)
        existing = self.conn.execute("SELECT * FROM jobs WHERE id=?", (job.id,)).fetchone()
        if existing is None:
            # Backward compatibility for databases populated with the old URL-based
            # IDs: compare the stable human identity before inserting a new row.
            candidates = self.conn.execute("SELECT * FROM jobs").fetchall()
            wanted = (canonical_company(job.company), canonical_title(job.title),
                      canonical_location(job.location))
            existing = next((r for r in candidates if (
                canonical_company(r["company"]), canonical_title(r["title"]),
                canonical_location(r["location"])) == wanted), None)
        if existing is not None:
            self._merge_existing(existing, job)
            self.conn.commit()
            return False
        self.conn.execute(
            """INSERT INTO jobs (id, source, company, title, location, url, jd_text,
               posted_at, first_seen, state, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (job.id, job.source, job.company, job.title, job.location, job.url,
             job.jd_text, job.posted_at, job.first_seen, job.state, job.updated_at),
        )
        self.conn.commit()
        return True

    def _merge_existing(self, existing: sqlite3.Row, incoming: Job) -> None:
        """Enrich discovery fields without resetting state, score, or first_seen."""
        current = dict(existing)
        jd_text = incoming.jd_text if len(incoming.jd_text or "") > len(current.get("jd_text") or "") else current.get("jd_text", "")
        posted_at = current.get("posted_at", "")
        if _date_quality(incoming.posted_at) > _date_quality(posted_at):
            posted_at = incoming.posted_at
        old_url = canonicalize_url(current.get("url", ""))
        new_url = canonicalize_url(incoming.url)
        url = new_url if _url_quality(new_url) > _url_quality(old_url) else old_url
        source = incoming.source if len(incoming.source or "") > len(current.get("source") or "") else current.get("source", "")
        self.conn.execute(
            """UPDATE jobs SET source=?, location=?, url=?, jd_text=?, posted_at=?, updated_at=?
               WHERE id=?""",
            (source, incoming.location or current.get("location", ""), url, jd_text,
             posted_at, now_iso(), current["id"]),
        )

    def set_score(self, job_id: str, score: int, score_json: dict) -> None:
        self.conn.execute(
            """UPDATE jobs SET score=?, score_json=?, scored_at=?,
               state=CASE WHEN state='discovered' THEN 'scored' ELSE state END,
               updated_at=? WHERE id=?""",
            (score, json.dumps(score_json), now_iso(), now_iso(), job_id),
        )
        self.conn.commit()

    def set_state(self, job_id: str, state: str, *, force: bool = False) -> None:
        if state not in STATES:
            raise ValueError(f"Unknown job state: {state}")
        current_row = self.conn.execute("SELECT state FROM jobs WHERE id=?", (job_id,)).fetchone()
        if current_row is None:
            raise KeyError(f"Unknown job ID: {job_id}")
        current = current_row["state"]
        if not force and state != current and state not in LEGAL_TRANSITIONS.get(current, set()):
            raise ValueError(f"Illegal job-state transition: {current} -> {state}")
        extra = ""
        if state == "applied":
            extra = ", applied_at='%s'" % now_iso()
        self.conn.execute(
            f"UPDATE jobs SET state=?, updated_at=?{extra} WHERE id=?",
            (state, now_iso(), job_id),
        )
        self.conn.commit()

    # ---- reads --------------------------------------------------------
    @staticmethod
    def _hydrate(row: dict) -> dict:
        d = dict(row)
        raw = d.get("score_json") or "{}"
        try:
            d["score_json"] = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            d["score_json"] = {}
        return d

    def _rows(self, where: str = "", args: tuple = ()) -> list[dict]:
        sql = "SELECT * FROM jobs"
        if where:
            sql += " WHERE " + where
        sql += " ORDER BY COALESCE(score,-1) DESC, first_seen DESC"
        return [self._hydrate(r) for r in self.conn.execute(sql, args).fetchall()]

    def by_state(self, state: str) -> list[dict]:
        return self._rows("state=?", (state,))

    def unscored(self) -> list[dict]:
        return self._rows("state='discovered'")

    def all(self) -> list[dict]:
        return self._rows()

    def get(self, job_id: str) -> dict | None:
        r = self.conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return self._hydrate(r) if r else None

    def counts(self) -> dict[str, int]:
        rows = self.conn.execute("SELECT state, COUNT(*) c FROM jobs GROUP BY state").fetchall()
        return {r["state"]: r["c"] for r in rows}


def _date_quality(value: str | None) -> int:
    text = (value or "").strip()
    if not text:
        return 0
    # Exact machine-readable dates are more useful than relative prose.
    if len(text) >= 10 and text[:4].isdigit() and text[4] == "-":
        return 3
    if any(ch.isdigit() for ch in text):
        return 2
    return 1


def _url_quality(value: str) -> int:
    if not value:
        return 0
    host = value.split("/", 3)[2].lower() if "://" in value else ""
    aggregator = any(name in host for name in
                     ("adzuna", "jsearch", "arbeitnow", "indeed", "linkedin"))
    return (2 if value.startswith("https://") else 1) + (0 if aggregator else 2)
