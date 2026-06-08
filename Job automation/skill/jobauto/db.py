"""SQLite pipeline store (stage 7). Stdlib sqlite3 only."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .models import Job, now_iso

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
        """Insert new job; if id exists, keep first_seen and skip. Returns True if new."""
        cur = self.conn.execute("SELECT id FROM jobs WHERE id=?", (job.id,))
        if cur.fetchone():
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

    def set_score(self, job_id: str, score: int, score_json: dict) -> None:
        self.conn.execute(
            "UPDATE jobs SET score=?, score_json=?, scored_at=?, state=?, updated_at=? WHERE id=?",
            (score, json.dumps(score_json), now_iso(), "scored", now_iso(), job_id),
        )
        self.conn.commit()

    def set_state(self, job_id: str, state: str) -> None:
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
