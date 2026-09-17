"""Run a writing-pipeline role through a headless agent CLI.

Each role runs in a private workspace outside the checkout.  The agent reads
inputs copied into that workspace and writes one JSON file back; the pipeline
code, not the agent, decides what happens next.  Two properties matter:

* **Isolation.**  A host CLI started inside a project tree picks up that
  tree's instruction files and hooks, which can hijack a headless run.  The
  default command therefore loads no user settings, disables hooks, and
  denies the shell and the web.  Set ``writer.workspace_root`` to a folder
  outside any project when your checkout lives inside one that has its own
  agent instructions.
* **Persistence.**  A role that is resumed with its session id keeps its own
  earlier reasoning, so a reviewer checking round two remembers what it asked
  for in round one.
"""
from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


@dataclass
class AgentResult:
    ok: bool
    session_id: str | None
    text: str = ""
    cost_usd: float = 0.0
    seconds: float = 0.0
    error: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class AgentRunner(Protocol):
    def run(self, role: str, prompt: str, workspace: Path, *, session_id: str | None = None) -> AgentResult: ...


DEFAULT_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]
DENIED_TOOLS = ["Bash", "PowerShell", "WebFetch", "WebSearch", "Agent", "Task", "NotebookEdit"]


class ClaudeCliRunner:
    """Claude Code in print mode.  The prompt goes over stdin, never argv."""

    def __init__(self, command: str = "claude", model: str | None = "opus", *,
                 timeout_s: int = 1800, max_budget_usd: float | None = None,
                 extra_args: list[str] | None = None):
        self.command = command
        self.model = model
        self.timeout_s = timeout_s
        self.max_budget_usd = max_budget_usd
        self.extra_args = list(extra_args or [])

    def _argv(self, session_id: str | None, workspace: Path) -> list[str]:
        exe = shutil.which(self.command) or self.command
        # A settings file, not inline JSON: on Windows the CLI is a .cmd shim and cmd.exe mangles quotes.
        settings = workspace / ".agent-settings.json"
        settings.write_text(json.dumps({"disableAllHooks": True}), encoding="utf-8")
        argv = [exe, "-p", "--output-format", "json",
                "--setting-sources", "project",
                "--settings", str(settings),
                "--permission-mode", "acceptEdits",
                "--allowedTools", ",".join(DEFAULT_TOOLS),
                "--disallowedTools", ",".join(DENIED_TOOLS)]
        if self.model:
            argv += ["--model", self.model]
        if self.max_budget_usd:
            argv += ["--max-budget-usd", str(self.max_budget_usd)]
        if session_id:
            argv += ["--resume", session_id]
        return argv + self.extra_args

    def run(self, role: str, prompt: str, workspace: Path, *, session_id: str | None = None) -> AgentResult:
        workspace.mkdir(parents=True, exist_ok=True)
        start = time.monotonic()
        group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
        try:
            proc = subprocess.Popen(self._argv(session_id, workspace), cwd=str(workspace), stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                    errors="replace", **group)
        except OSError as exc:
            return AgentResult(False, session_id, error=f"{role}: could not start {self.command!r}: {exc}",
                               seconds=time.monotonic() - start)
        try:
            stdout, stderr = proc.communicate(prompt, timeout=self.timeout_s)
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            return AgentResult(False, session_id, error=f"{role}: timed out after {self.timeout_s}s",
                               seconds=time.monotonic() - start)
        done = subprocess.CompletedProcess(proc.args, proc.returncode, stdout, stderr)
        seconds = time.monotonic() - start
        try:
            payload = json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {}
        except (ValueError, IndexError):
            payload = {}
        if not payload:
            tail = (done.stderr or done.stdout or "").strip()[-600:]
            return AgentResult(False, session_id, error=f"{role}: exit {done.returncode}, no result: {tail}",
                               seconds=seconds)
        return AgentResult(
            ok=not payload.get("is_error") and done.returncode == 0,
            session_id=payload.get("session_id") or session_id,
            text=str(payload.get("result") or ""),
            cost_usd=float(payload.get("total_cost_usd") or 0.0),
            seconds=seconds,
            error="" if not payload.get("is_error") else f"{role}: {payload.get('subtype')}: {payload.get('result')}",
            raw={k: payload.get(k) for k in ("subtype", "num_turns", "terminal_reason", "permission_denials")},
        )


def _kill_tree(proc: subprocess.Popen) -> None:
    """On Windows the CLI is a .cmd shim, so killing the direct child leaves the agent running."""
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, check=False)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except OSError:
        proc.kill()
    try:
        proc.communicate(timeout=10)
    except (subprocess.TimeoutExpired, ValueError):
        pass


def claude_available(command: str = "claude") -> bool:
    return shutil.which(command) is not None


def runner_from_config(settings: dict[str, Any]) -> ClaudeCliRunner:
    agent = settings.get("agent") or {}
    return ClaudeCliRunner(
        command=agent.get("command", "claude"),
        model=agent.get("model", "opus"),
        timeout_s=int(agent.get("timeout_s", 1800)),
        max_budget_usd=agent.get("max_budget_usd_per_call"),
        extra_args=agent.get("extra_args") or [],
    )
