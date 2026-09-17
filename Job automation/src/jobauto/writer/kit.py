"""The application kit: one folder per job that any coding agent can work in.

``prepare`` builds::

    Applications/<company-title>/
      PROMPT.md       paste this into your agent (Claude Code, Codex, Cursor, Gemini CLI, ...)
      job.json        the job record
      status.json     written only by the gates
      questions.md    what only the candidate can answer
      final/          the upload-named PDFs once the review passes
      reviews/        every review, per round
      templates/      renderer output per template
      workspace/      where the agents work
        roles/          planner.md, writer.md, reviewer.md
        job/job.md      the job description (paste the full text here if it is truncated)
        facts/          copies of the candidate's fact files
        skills/         writing and reviewing rules
        examples/       approved applications to match in quality
        schema/         JSON shapes
        plan.json, content.json, review.json   written by the roles
        rounds/rN/      rendered PDFs, page images, machine QA and manifest per round
        FEEDBACK.md     the latest feedback for the role that has to act
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from .. import config
from . import SCHEMA, prompts
from .facts import clean_job_text, load_fact_corpus
from .plan import PLAN_SCHEMA
from .schema import CONTENT_SCHEMA, REVIEW_SCHEMA

DEFAULTS: dict[str, Any] = {
    "templates": ["rendercv-sb2nov"],
    "resume_pages": 2,
    "max_review_rounds": 3,
    "max_fix_attempts": 3,
    "min_scores": {"content": 90, "design": 90},
    "hold_on_weak_fit": True,
    "workspace_root": "",
    "examples_dir": "",
    "agent": {"command": "claude", "model": "opus", "timeout_s": 1800},
}
SKILL_NAMES = ("house-style", "jd-evidence-planner", "resume-writer", "cover-letter-writer", "application-reviewer")
TERMINAL = ("docs_ready", "hold", "needs_operator")
MIN_JD_CHARS = 800


def settings_from_config(cfgd: dict[str, Any] | None = None) -> dict[str, Any]:
    cfgd = cfgd if cfgd is not None else config.load_config()
    merged = {**DEFAULTS, **(cfgd.get("writer") or {})}
    merged["min_scores"] = {**DEFAULTS["min_scores"], **(merged.get("min_scores") or {})}
    merged["agent"] = {**DEFAULTS["agent"], **(merged.get("agent") or {})}
    return merged


def parse_templates(names: list[str]) -> tuple[list[str], list[str]]:
    html, rcv = [], []
    for name in names:
        engine, _, theme = str(name).partition("-")
        if engine == "html" and theme:
            html.append(theme)
        elif engine == "rendercv" and theme:
            rcv.append(theme)
        else:
            raise ValueError(f"template {name!r} must look like 'html-<theme>' or 'rendercv-<theme>'")
    return html, rcv


# ----------------------------------------------------------------------------- files

def read_json(path: Path) -> tuple[Any, str]:
    if not path.is_file():
        return None, f"{path.name} was not written"
    try:
        return json.loads(path.read_text(encoding="utf-8")), ""
    except ValueError as exc:
        return None, f"{path.name} is not valid JSON: {exc}"


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def load_status(app_dir: Path) -> dict[str, Any]:
    data, _ = read_json(app_dir / "status.json")
    return data if isinstance(data, dict) else {}


def save_status(app_dir: Path, status: dict[str, Any]) -> None:
    status["updated_at"] = now()
    write_json(app_dir / "status.json", status)


def log_event(status: dict[str, Any], gate: str, ok: bool, note: str) -> None:
    status.setdefault("history", []).append({"at": now(), "gate": gate, "ok": ok, "note": note})


# ------------------------------------------------------------------------ locations

def application_dir(job: dict[str, Any], root: Path | None = None) -> Path:
    """The folder whose job.json carries this id; otherwise a new slug."""
    root = root or config.applications_dir()
    existing = find_by_job_id(job["id"], root)
    if existing:
        return existing
    base = re.sub(r"[^a-z0-9]+", "-", f"{job.get('company', '')}-{job.get('title', '')}".lower()).strip("-")
    base = (base or "application")[:60].strip("-")
    candidate, suffix = root / base, 2
    while candidate.exists():
        candidate, suffix = root / f"{base}-{suffix}", suffix + 1
    return candidate


def find_by_job_id(job_id: str, root: Path | None = None) -> Path | None:
    root = root or config.applications_dir()
    if not root.is_dir():
        return None
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        data, _ = read_json(folder / "job.json")
        if isinstance(data, dict) and data.get("id") == job_id:
            return folder
    return None


def resolve(ref: str | Path) -> Path:
    """An application folder from its path or its job id."""
    path = Path(ref).expanduser()
    if (path / "job.json").is_file():
        return path.resolve()
    found = find_by_job_id(str(ref))
    if found:
        return found
    raise FileNotFoundError(f"no application folder for {ref!r}; run `jobauto app prepare <job_id>` first")


def workspace_of(app_dir: Path) -> Path:
    ws = load_status(app_dir).get("workspace")
    return Path(ws) if ws else app_dir / "workspace"


def _workspace_for(app_dir: Path, job: dict[str, Any], settings: dict[str, Any]) -> Path:
    if settings.get("workspace_root"):
        return Path(settings["workspace_root"]).expanduser().resolve() / job["id"]
    return app_dir / "workspace"


# -------------------------------------------------------------------------- prepare

def job_text(job: dict[str, Any]) -> str:
    header = (f"# {job.get('company', '')}: {job.get('title', '')}\n\n- Location: {job.get('location', '')}\n"
              f"- Posting: {job.get('url', '')}\n\n")
    return header + clean_job_text(job.get("jd_text", ""))


def _copy_examples(ws: Path, settings: dict[str, Any]) -> list[str]:
    target = ws / "examples"
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    source = Path(settings["examples_dir"]).expanduser() if settings.get("examples_dir") \
        else config.profile_dir() / "writer_examples"
    files = sorted(source.glob("*.json"))[:3] if source.is_dir() else []
    if not files:
        bundled = config.CHECKOUT_DIR / "examples" / "sample-candidate" / "content.json"
        files = [bundled] if bundled.is_file() else []
    for path in files:
        shutil.copy2(path, target / path.name)
    return [p.name for p in files]


def refresh_inputs(ws: Path, settings: dict[str, Any]) -> dict[str, Any]:
    """Copy the parts an agent must never edit: roles, facts, skills, schema, examples."""
    for name in ("roles", "facts", "skills", "schema"):
        if (ws / name).exists():
            shutil.rmtree(ws / name)
    (ws / "roles").mkdir(parents=True)
    for role, text in prompts.ROLES.items():
        (ws / "roles" / f"{role}.md").write_text(text, encoding="utf-8")
    (ws / "facts").mkdir()
    corpus = load_fact_corpus()
    for source in corpus.sources:
        shutil.copy2(source, ws / "facts" / Path(source).name)
    for name in SKILL_NAMES:
        src = config.skills_dir() / name
        if src.is_dir():
            shutil.copytree(src, ws / "skills" / name, ignore=shutil.ignore_patterns("*.ttf", "OFL.txt"))
    write_json(ws / "schema" / "plan_schema.json", PLAN_SCHEMA)
    write_json(ws / "schema" / "content_schema.json", CONTENT_SCHEMA)
    write_json(ws / "schema" / "review_schema.json", REVIEW_SCHEMA)
    return {"facts": [Path(s).name for s in corpus.sources], "examples": _copy_examples(ws, settings)}


def candidate_problems() -> list[str]:
    master = config.profile_dir() / "master_resume.yml"
    if not master.is_file():
        return [f"{master} is missing: run `jobauto init` and fill it with your own facts"]
    text = master.read_text(encoding="utf-8", errors="replace")
    if "Your Name" in text or "<your name>" in text.lower():
        return [f"{master} still contains the placeholder name: replace it with your own facts"]
    return []


def prepare(job: dict[str, Any], settings: dict[str, Any] | None = None, *, redo: bool = False) -> dict[str, Any]:
    """Create or refresh the application kit for one job.  Returns its paths and warnings."""
    settings = settings or settings_from_config()
    problems = candidate_problems()
    if problems:
        raise ValueError("; ".join(problems))
    parse_templates(settings["templates"])
    app_dir = application_dir(job)
    status = load_status(app_dir)
    if redo or not status:
        for name in ("final", "reviews", "templates", "questions.md", "status.json"):
            target = app_dir / name
            if target.is_dir():
                shutil.rmtree(target)
            elif target.exists():
                target.unlink()
        old_ws = Path(status["workspace"]) if status.get("workspace") else None
        if old_ws and old_ws.exists():
            shutil.rmtree(old_ws)
        status = {}
    app_dir.mkdir(parents=True, exist_ok=True)
    ws = Path(status.get("workspace") or _workspace_for(app_dir, job, settings))
    ws.mkdir(parents=True, exist_ok=True)
    write_json(app_dir / "job.json", job)
    job_md = ws / "job" / "job.md"
    if not job_md.is_file():
        job_md.parent.mkdir(parents=True, exist_ok=True)
        job_md.write_text(job_text(job), encoding="utf-8")
    inputs = refresh_inputs(ws, settings)

    warnings = []
    if len(clean_job_text(job.get("jd_text", ""))) < MIN_JD_CHARS:
        warnings.append(f"the job description is short ({len(job.get('jd_text') or '')} characters) and may be "
                        f"truncated: paste the full posting into {job_md} before starting")
    if not inputs["examples"]:
        warnings.append("no example applications found; the writer works from the skills alone")

    if not status:
        status = {"schema": SCHEMA, "job_id": job["id"], "company": job.get("company"), "title": job.get("title"),
                  "url": job.get("url"), "created_at": now(), "stage": "prepared", "result": None, "round": 1,
                  "attempts": {"plan": 0, "render": 0}, "templates": settings["templates"],
                  "workspace": str(ws), "reviews": [], "final_pdfs": [], "history": []}
        log_event(status, "prepare", True, f"facts: {', '.join(inputs['facts'])}")
    status["warnings"] = warnings
    save_status(app_dir, status)
    prompt = build_prompt(app_dir, ws, job, settings)
    (app_dir / "PROMPT.md").write_text(prompt, encoding="utf-8")
    return {"app_dir": str(app_dir), "workspace": str(ws), "prompt_path": str(app_dir / "PROMPT.md"),
            "prompt": prompt, "warnings": warnings, "status": status}


# --------------------------------------------------------------------------- prompt

def gate_commands(app_dir: Path) -> dict[str, str]:
    """Shell commands for each gate, for the shells an agent is likely to use."""
    python, root = sys.executable, config.project_root()
    base = f'"{python}" -m jobauto --home "{root}" app {{action}} "{app_dir}"'
    forms = {"shell": base}
    if os.name == "nt":
        forms["powershell"] = "& " + base
    return forms


def build_prompt(app_dir: Path, ws: Path, job: dict[str, Any], settings: dict[str, Any]) -> str:
    forms = gate_commands(app_dir)

    def cmd(action: str) -> str:
        lines = [f"    {forms['shell'].format(action=action)}"]
        if "powershell" in forms:
            lines = [f"    # bash, zsh or cmd", lines[0], "    # PowerShell",
                     f"    {forms['powershell'].format(action=action)}"]
        return "\n".join(lines)

    fixes, rounds = settings["max_fix_attempts"], settings["max_review_rounds"]
    return f"""# Application task: {job.get('company', '')} - {job.get('title', '')}

You are orchestrating a job-application workflow for the person who gave you this prompt. Three roles
do the work - **planner**, **writer**, **reviewer** - and code **gates** between them decide whether the
work may move on. You coordinate; you do not write or judge the documents yourself.

- Workspace: `{ws}`
- Application folder: `{app_dir}`
- Role instructions: `roles/planner.md`, `roles/writer.md`, `roles/reviewer.md` inside the workspace.
  All paths in them are relative to the workspace.

## Rules

1. Nothing is ever sent to an employer. You only produce documents.
2. Never edit `facts/`, `skills/`, `schema/`, `roles/`, `rounds/`, `status.json` or any `manifest.json`.
   Never edit `content.json` or `review.json` as the orchestrator: send the work back to its role.
3. Use subagents when your tool has them (Claude Code: the Task/Agent tool; Codex: a spawned agent;
   otherwise a new chat in the same folder). Start each role with exactly:

   > Your working directory is `{ws}`. Read `roles/<role>.md` and do exactly what it says. If
   > `FEEDBACK.md` exists, read it first.

   The reviewer must never be the agent that wrote `content.json`. Reuse the same writer and the same
   reviewer across rounds when your tool allows it.
4. No subagents? Play the roles one after another. Before reviewing, re-read `roles/reviewer.md` and judge
   the PDFs and page images as a strict stranger would. Do not defend your own writing.
5. Every gate prints `RESULT:` and `NEXT:` lines. Do what `NEXT:` says.

## Steps

**1. Plan.** Run the planner, then the plan gate:

{cmd('check-plan')}

If it fails, send the planner back (it reads `FEEDBACK.md`). After {fixes} failed fixes, stop and report.

**2. Write.** Run the writer, then the render gate (fact lock, PDF rendering, PDF QA):

{cmd('render')}

If it fails, send the writer back. After {fixes} failed fixes in a round, stop and report.

**3. Review.** Run the reviewer, then the finalize gate:

{cmd('finalize')}

- `RESULT: docs_ready` - done.
- `RESULT: revise` - the writer revises from `FEEDBACK.md`, run `render`, the reviewer reviews again, run
  `finalize`. At most {rounds} review rounds in total.
- `RESULT: hold` - the documents passed, but the fit is weak or an eligibility requirement is not met.
  Stop: the candidate decides.
- `RESULT: needs_operator` - stop.

**4. Report** to the person: the result, the PDFs in `{app_dir / 'final'}`, the open questions in
`{app_dir / 'questions.md'}`, and the review scores. This prints a summary:

{cmd('status')}
"""
