"""Per-source run accounting: attempted / ok / failed / jobs_yielded, and history.

Three defects in this project were the same defect: a source that could not run
returned an empty list and the report presented the zero as success.

* ``fetch_jobspy`` caught ``ImportError``, printed one line to stdout and
  returned ``[]``.  Inside a scheduled run nobody reads stdout, so the configured
  *primary* discovery source was dead for weeks while every report said the run
  was healthy.
* ``fetch_recipe`` returned ``[]`` for every ``portal: custom`` company.
* The Personio feed lost every posting date to a case-folding parser.

The rule this module enforces: **a source that cannot run is a recorded failure
with a reason, never an empty list.**  Counting only ``ok``/``failed`` is not
enough either -- an ATS board that answers HTTP 200 with zero postings is the
58-companies-zero-jobs case, and it looked identical to a healthy board.  So
every record carries ``jobs_yielded`` as well, history is appended rather than
overwritten, and a source that has yielded nothing across its last three
recorded runs is flagged in the report.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

#: Number of consecutive zero-yield runs after which a source is flagged.
ZERO_YIELD_RUNS = 3

HISTORY_FILENAME = "source_history.jsonl"

_RECORD_KEYS = ("run_id", "utc", "source", "attempted", "ok", "failed", "jobs_yielded")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def make_record(source: str, *, attempted: bool = True, ok: bool = False,
                jobs_yielded: int = 0, status: str = "", error: str = "",
                run_id: str = "", **extra: Any) -> dict:
    """One source's outcome for one run, in the schema AC-12 pins.

    ``ok`` is never inferred from an empty result: a caller that got no postings
    and no exception must still say whether the source *ran*.
    """
    yielded = int(jobs_yielded)
    # A source that returned no postings is never a successful source check,
    # even if a caller accidentally passes ``ok=True`` after an HTTP 200.  This
    # keeps the invariant at the ledger boundary, not only in individual fetch
    # adapters.
    healthy = bool(ok and yielded > 0)
    record = {
        "run_id": run_id or "",
        "utc": utc_now(),
        "source": source,
        "attempted": bool(attempted),
        "ok": healthy,
        "failed": bool(attempted and not healthy),
        "jobs_yielded": yielded,
    }
    if status:
        record["status"] = status
    if error:
        record["error"] = str(error)[:400]
    # Outcome fields are part of the contract and cannot be overwritten by a
    # source-specific diagnostic payload.
    record.update({key: value for key, value in extra.items()
                   if key not in _RECORD_KEYS})
    return record


class SourceRun:
    """The per-source ledger for one execution of the fetch stage."""

    def __init__(self, run_id: str | None = None) -> None:
        self.run_id = run_id or new_run_id()
        self.records: list[dict] = []
        self._bound: dict | None = None

    # -- recording -------------------------------------------------------
    def record(self, source: str, **kwargs: Any) -> dict:
        entry = make_record(source, run_id=self.run_id, **kwargs)
        self.records.append(entry)
        if self._bound is not None:
            self._refresh(self._bound)
        return entry

    def ok(self, source: str, jobs_yielded: int, **extra: Any) -> dict:
        return self.record(source, attempted=True, ok=True,
                           jobs_yielded=int(jobs_yielded),
                           status=extra.pop("status", "ok"), **extra)

    def failure(self, source: str, error: str, status: str = "failed", **extra: Any) -> dict:
        return self.record(source, attempted=True, ok=False, jobs_yielded=0,
                           status=status, error=error, **extra)

    def skipped(self, source: str, reason: str, **extra: Any) -> dict:
        """A source that was deliberately not run - disabled, or no credential.

        A skip is ``attempted: false``: it is neither a success nor a fault, but
        it is still recorded, because "we never asked" and "we asked and got
        nothing" are different facts about a report.
        """
        return self.record(source, attempted=False, ok=False, jobs_yielded=0,
                           status="skipped", error=reason, **extra)

    # -- reporting -------------------------------------------------------
    def summary(self) -> dict:
        attempted = [r for r in self.records if r["attempted"]]
        return {
            "run_id": self.run_id,
            "utc": utc_now(),
            "attempted": len(attempted),
            "successful": sum(1 for r in attempted if r["ok"]),
            "failed": sum(1 for r in attempted if r["failed"]),
            "skipped": sum(1 for r in self.records if not r["attempted"]),
            # Kept for the operational probes that read source_run.json. It now
            # counts only sources genuinely handed to the agent backend, not the
            # 58 companies the old code silently filed here.
            "agent_only": sum(1 for r in self.records if r.get("status") == "agent_only"),
            "postings": sum(r["jobs_yielded"] for r in self.records),
            "empty_successes": sorted(
                r["source"] for r in self.records if r["ok"] and r["jobs_yielded"] == 0),
            "failures": [
                {"source": r["source"], "status": r.get("status", "failed"),
                 "error": r.get("error", "")}
                for r in self.records if r["failed"]
            ],
            "results": self.records,
        }

    def _refresh(self, health: dict) -> dict:
        summary = self.summary()
        for key in ("run_id", "attempted", "successful", "failed", "skipped",
                    "agent_only", "postings", "empty_successes", "failures"):
            health[key] = summary[key]
        health["results"] = self.records
        health["healthy"] = summary["successful"] > 0
        return health

    def bind(self, health: dict) -> dict:
        """Keep `health` in step with this ledger for the rest of the run.

        The fetch stage builds its health summary, hands it to the caller, and
        only *then* runs the sources that have their own fetch path (JobSpy).
        Without this binding those sources' outcomes are recorded after the
        summary was taken and never reach ``source_run.json`` - which is exactly
        how a dead primary source stayed invisible.
        """
        self._bound = health
        return self._refresh(health)

    def merge_into(self, health: dict) -> dict:
        """Fold this ledger into an existing health dict, in place."""
        return self._refresh(health)


# ------------------------------------------------------------------ history


def history_path(data_dir: Path | None = None) -> Path:
    """Where run history is appended.

    Deliberately outside ``output/``: that directory is regenerated and
    gitignored, so a history kept there answers "has this source been dead for
    three runs?" with "I do not remember".
    """
    if data_dir is None:
        from .. import config
        data_dir = config.profile_dir()
    return Path(data_dir) / HISTORY_FILENAME


def append_history(records: Iterable[dict], path: Path | None = None) -> Path:
    """Append records as JSON Lines.  Never truncates, never rewrites."""
    target = Path(path) if path is not None else history_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8", newline="\n") as fh:
        for record in records:
            # Keep the append-only history intentionally small and stable. The
            # required schema is exactly these seven fields; transient diagnosis
            # remains in the run report's richer record.
            payload = {k: record.get(k) for k in _RECORD_KEYS}
            fh.write(json.dumps(payload, ensure_ascii=False) + "\n")
    return target


def read_history(path: Path | None = None) -> list[dict]:
    target = Path(path) if path is not None else history_path()
    if not target.exists():
        return []
    out: list[dict] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def zero_yield_sources(path: Path | None = None, runs: int = ZERO_YIELD_RUNS,
                       history: list[dict] | None = None) -> list[str]:
    """Sources whose last `runs` **appended** records all yielded zero postings.

    A source with fewer than `runs` records is not flagged: one bad afternoon is
    not evidence, and a check that fires on the first empty run gets muted.
    """
    entries = history if history is not None else read_history(path)
    by_source: dict[str, list[dict]] = {}
    for entry in entries:
        name = entry.get("source")
        if not name:
            continue
        by_source.setdefault(str(name), []).append(entry)
    flagged = []
    for name, records in by_source.items():
        recent = records[-runs:]
        if len(recent) < runs:
            continue
        if all(int(r.get("jobs_yielded") or 0) == 0 for r in recent):
            flagged.append(name)
    return sorted(flagged)


# ------------------------------------------------- the ledger of the live run

_ACTIVE: SourceRun | None = None


def active_run() -> SourceRun | None:
    return _ACTIVE


def start_run(run_id: str | None = None) -> SourceRun:
    global _ACTIVE
    _ACTIVE = SourceRun(run_id)
    return _ACTIVE


def end_run() -> None:
    global _ACTIVE
    _ACTIVE = None


def record_on_active(source: str, **kwargs: Any) -> dict | None:
    """Record against the run in progress, if there is one.

    This is what lets a source that runs *after* the health summary was built --
    JobSpy, today -- still appear in the written report instead of vanishing.
    """
    run = _ACTIVE
    if run is None:
        return None
    return run.record(source, **kwargs)


def history_enabled() -> bool:
    """History writing can be turned off for tests and for dry runs."""
    return os.environ.get("JOBAUTO_NO_HISTORY", "").strip().lower() not in ("1", "true", "yes")
