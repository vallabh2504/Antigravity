"""Run the application workflow headlessly: the same kit, roles and gates as PROMPT.md.

For each approved job: prepare the kit, then planner -> ``check_plan`` ->
writer -> ``render`` -> reviewer -> ``finalize``, looping on the gates' verdicts.
Each role keeps one agent session for the whole job, so the reviewer of round
two remembers what it asked for in round one, and the reviewer never shares a
session with the writer.  Nothing is ever submitted.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from ..db import DB
from . import gates, kit, prompts
from .agents import AgentResult, AgentRunner

Log = Callable[[str], None]


def _record(app_dir: Path, role: str, result: AgentResult, log: Log) -> None:
    status = kit.load_status(app_dir)
    status["cost_usd"] = round(float(status.get("cost_usd") or 0) + result.cost_usd, 4)
    status.setdefault("agent_steps", []).append({
        "at": kit.now(), "role": role, "ok": result.ok, "seconds": round(result.seconds),
        "cost_usd": round(result.cost_usd, 4), "session_id": result.session_id, "error": result.error})
    kit.save_status(app_dir, status)
    log(f"  {role}: {'ok' if result.ok else 'FAILED'} {round(result.seconds)}s ${result.cost_usd:.2f} {result.error}")


def _finish(app_dir: Path, result: str, log: Log, **extra: Any) -> dict[str, Any]:
    status = kit.load_status(app_dir)
    if status.get("result") not in kit.TERMINAL:  # a gate's final verdict is never overwritten
        status.update(result=result, **extra)
    status["finished_at"] = kit.now()
    kit.save_status(app_dir, status)
    log(f"  result: {status['result']}")
    return {**status, "application_dir": str(app_dir)}


def _gate(name: str, outcome: dict[str, Any], log: Log) -> dict[str, Any]:
    detail = outcome.get("findings") or outcome.get("problems") or outcome.get("reasons") or []
    log(f"  gate {name}: {outcome['result']}")
    for item in detail[:12]:
        log(f"    - {item.get('where', '')}: {item.get('message', '')}" if isinstance(item, dict) else f"    - {item}")
    return outcome


def write_application(job: dict[str, Any], db: DB, runner: AgentRunner, settings: dict[str, Any], *,
                      redo: bool = False, log: Log = print) -> dict[str, Any]:
    prepared = kit.prepare(job, settings, redo=redo)
    app_dir, ws = Path(prepared["app_dir"]), Path(prepared["workspace"])
    for warning in prepared["warnings"]:
        log(f"  warning: {warning}")
    sessions: dict[str, str | None] = {"planner": None, "writer": None, "reviewer": None}

    def run(role: str) -> AgentResult:
        result = runner.run(role, prompts.role_call(role), ws, session_id=sessions[role])
        sessions[role] = result.session_id or sessions[role]
        _record(app_dir, role, result, log)
        return result

    status = kit.load_status(app_dir)
    if status.get("result") in kit.TERMINAL:
        return _finish(app_dir, status["result"], log)

    if status.get("stage") == "prepared":
        while True:
            if not run("planner").ok:
                return _finish(app_dir, "agent_failed", log, reason="planner failed")
            outcome = _gate("check-plan", gates.check_plan(app_dir, db, settings), log)
            if outcome["ok"]:
                break
            if outcome["result"] in kit.TERMINAL:
                return _finish(app_dir, outcome["result"], log)

    while True:
        outcome = {"ok": kit.load_status(app_dir).get("stage") == "rendered"}
        while not outcome["ok"]:
            if not run("writer").ok:
                return _finish(app_dir, "agent_failed", log, reason="writer failed")
            outcome = _gate("render", gates.render(app_dir, db, settings), log)
            if outcome["result"] in kit.TERMINAL:
                return _finish(app_dir, outcome["result"], log)
            if outcome["result"] == "fix_plan":
                return _finish(app_dir, "needs_operator", log, reason="the plan no longer passes its gate")
        if not run("reviewer").ok:
            return _finish(app_dir, "agent_failed", log, reason="reviewer failed")
        outcome = _gate("finalize", gates.finalize(app_dir, db, settings), log)
        if outcome["result"] in kit.TERMINAL:
            return _finish(app_dir, outcome["result"], log)
        if outcome["result"] != "revise":
            # review.json missing or PDFs changed: one more reviewer attempt, then hand over.
            if not run("reviewer").ok:
                return _finish(app_dir, "agent_failed", log, reason="reviewer failed")
            outcome = _gate("finalize", gates.finalize(app_dir, db, settings), log)
            if outcome["result"] in kit.TERMINAL:
                return _finish(app_dir, outcome["result"], log)
            if outcome["result"] != "revise":
                return _finish(app_dir, "needs_operator", log, reason=outcome.get("next", "finalize failed"))


def pending_jobs(db: DB, job_ids: list[str] | None = None, *, redo: bool = False) -> list[dict[str, Any]]:
    """Approved jobs whose application has not reached a final result (failed runs are retried)."""
    if job_ids:
        jobs = [j for j in (db.get(i) for i in job_ids) if j]
    else:
        jobs = sorted(db.by_state("approved") + db.by_state("docs_review"),
                      key=lambda j: j.get("score") or 0, reverse=True)
    pending = []
    for job in jobs:
        if job["state"] not in ("approved", "docs_review"):
            continue
        folder = kit.find_by_job_id(job["id"])
        finished = folder is not None and kit.load_status(folder).get("result") in kit.TERMINAL
        if redo or not finished:
            pending.append(job)
    return pending


def run(db: DB, runner: AgentRunner, settings: dict[str, Any], *, job_ids: list[str] | None = None,
        max_jobs: int = 1, redo: bool = False, log: Log = print) -> list[dict[str, Any]]:
    jobs = pending_jobs(db, job_ids, redo=redo)[:max(0, max_jobs)]
    log(f"autopilot: {len(jobs)} job(s), templates {settings['templates']}")
    results = []
    for job in jobs:
        log(f"- {job['id']} {job.get('company')}: {job.get('title')}")
        try:
            results.append(write_application(job, db, runner, settings, redo=redo, log=log))
        except Exception as exc:  # one broken job must not stop the others
            log(f"  error: {type(exc).__name__}: {exc}")
            results.append({"job_id": job["id"], "company": job.get("company"), "result": "error",
                            "error": f"{type(exc).__name__}: {exc}"})
    return results
