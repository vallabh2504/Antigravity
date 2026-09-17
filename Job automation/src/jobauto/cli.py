"""jobauto command line.

    jobauto init                      create your private profile files
    jobauto doctor                    check this machine
    jobauto fetch                     discover postings from your sources
    jobauto score                     rank them with the free rule-based scorer
    jobauto report                    write today's Markdown digest
    jobauto jobs [--state scored]     list jobs
    jobauto approve|reject <id>...    your decision on a job
    jobauto serve [--open]            the dashboard
    jobauto app prepare <id>          build the application kit and PROMPT.md
    jobauto app check-plan|render|finalize|status <app>   the gates an agent runs
    jobauto autopilot [<id>...]       run the whole application workflow with the Claude CLI
    jobauto templates <content.json>  render one content.json in every template to compare
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path


def _db():
    from . import config
    from .db import DB

    return DB(config.db_path())


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


# ---------------------------------------------------------------------- setup

def cmd_init(args) -> None:
    from . import config

    target = config.profile_dir()
    target.mkdir(parents=True, exist_ok=True)
    created = []
    for name in ("config.yml", "companies.yml", "master_resume.yml", "secrets.yml"):
        destination = target / name
        if destination.exists() and not args.force:
            continue
        shutil.copy2(config.example_path(name), destination)
        created.append(name)
    for name in ("profile.md", "writer_answers.md"):
        destination = target / name
        if not destination.exists():
            destination.write_text(f"<!-- {name}: facts about you in your own words. The writer may use every "
                                   f"sentence here, so keep it true. -->\n", encoding="utf-8")
            created.append(name)
    print(f"profile folder: {target}")
    print("created: " + (", ".join(created) if created else "nothing, your files were kept"))
    print("next: fill master_resume.yml and config.yml, then run `jobauto doctor`.")


def cmd_doctor(args) -> None:
    import importlib
    import platform

    from . import config
    from .pdf import find_browser
    from .writer import kit
    from .writer.agents import claude_available
    from .writer.render import find_pdftoppm
    from .writer.rendercv_engine import find_rendercv_python

    problems: list[str] = []

    def line(state: str, text: str) -> None:
        print(f"  {state:<8}{text}")

    print(f"python {platform.python_version()} ({sys.executable})")
    print(f"project {config.project_root()}")
    print("packages")
    for module, dist in (("yaml", "PyYAML"), ("bs4", "beautifulsoup4"), ("httpx", "httpx"), ("fastapi", "fastapi"),
                         ("uvicorn", "uvicorn"), ("pypdf", "pypdf"), ("pdfplumber", "pdfplumber"),
                         ("pypdfium2", "pypdfium2")):
        try:
            importlib.import_module(module)
            line("ok", dist)
        except Exception as exc:
            problems.append(f"{dist} is not installed: pip install -e .")
            line("MISSING", f"{dist}: {exc}")
    try:
        importlib.import_module("jobspy")
        line("ok", "python-jobspy (optional)")
    except Exception:
        line("absent", "python-jobspy (optional: pip install -e .[jobspy], Python 3.12 or older)")

    print("rendering")
    settings = kit.settings_from_config()
    html, rcv = kit.parse_templates(settings["templates"])
    browser = find_browser()
    line("ok" if browser else ("MISSING" if html else "absent"), f"Chrome or Edge: {browser or 'not found'}")
    if html and not browser:
        problems.append("an HTML template is selected but no Chrome or Edge was found")
    rendercv = find_rendercv_python()
    line("ok" if rendercv else ("MISSING" if rcv else "absent"), f"rendercv interpreter: {rendercv or 'not found'}")
    if rcv and not rendercv:
        problems.append("a rendercv template is selected but rendercv is missing: see README, 'Install'")
    pdftoppm = find_pdftoppm()
    line("ok" if pdftoppm else "WARN", f"pdftoppm (page images for the reviewer): {pdftoppm or 'not found'}")
    line("ok", f"templates: {', '.join(settings['templates'])}")

    print("agents")
    command = settings["agent"]["command"]
    line("ok" if claude_available(command) else "absent",
         f"{command} CLI for `jobauto autopilot` (not needed for PROMPT.md)")

    print("profile")
    folder = config.profile_dir()
    line("", str(folder))
    for name in ("config.yml", "companies.yml"):
        line("ok" if (folder / name).is_file() else "absent", name + ("" if (folder / name).is_file()
                                                                     else " (using the example)"))
    for problem in kit.candidate_problems():
        problems.append(problem)
        line("ACTION", problem)
    if not kit.candidate_problems():
        line("ok", "master_resume.yml")

    if problems:
        print("\nnot ready:")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)
    print("\nready.")


# ------------------------------------------------------------------ discovery

def run_fetch(log=print) -> dict:
    from . import config
    from .normalize import ingest
    from .sources import build_recipes
    from .sources import health as source_health
    from .sources.aggregators import build_aggregator_recipes
    from .sources.fetch import fetch_all_with_health
    from .sources.jobspy_source import fetch_jobspy
    from .util import age_days, contains_keyword

    cfgd = config.load_config()
    recipes = build_recipes(config.load_companies(), cfgd) + build_aggregator_recipes(cfgd, config.load_secrets())
    run = source_health.start_run()
    try:
        raws, health = fetch_all_with_health(recipes, run=run)
        jobspy_rows = fetch_jobspy(cfgd, int(cfgd.get("max_age_days", 3)))
        raws += jobspy_rows
        health["jobspy_postings"] = len(jobspy_rows)
        if source_health.history_enabled():
            source_health.append_history(run.records)
        health["zero_yield_sources"] = source_health.zero_yield_sources(history=source_health.read_history())
        (config.output_dir() / "source_run.json").write_text(json.dumps(health, indent=2), encoding="utf-8")
    finally:
        source_health.end_run()

    include, exclude = cfgd.get("include_keywords") or [], cfgd.get("exclude_keywords") or []
    max_age, strict = cfgd.get("max_age_days"), cfgd.get("strict_freshness", True)
    kept, off_topic, stale = [], 0, 0
    for raw in raws:
        text = f"{raw.title} {raw.jd_text}".lower()
        if (include and not any(contains_keyword(text, k) for k in include)) or \
                any(contains_keyword(text, k) for k in exclude):
            off_topic += 1
            continue
        age = age_days(raw.posted_at)
        if max_age is not None and ((age is None and strict) or (age is not None and age > max_age)):
            stale += 1
            continue
        kept.append(raw)
    result = ingest(_db(), kept)
    summary = {"fetched": len(raws), "kept": len(kept), "off_topic": off_topic, "stale": stale,
               "new": result["new"], "duplicates": result["dup"],
               "sources_ok": health.get("successful", 0), "sources_failed": health.get("failed", 0)}
    log(f"fetched {summary['fetched']} -> kept {summary['kept']} ({off_topic} off-topic, {stale} too old) "
        f"-> new {summary['new']}, duplicates {summary['duplicates']}")
    if not (health.get("successful") or jobspy_rows):
        log("warning: no source succeeded; see output/source_run.json")
    return summary


def cmd_fetch(args) -> None:
    run_fetch()


def run_score(limit: int = 500, log=print) -> int:
    from . import config, score

    count = score.auto_score(_db(), config.load_config(), limit)
    log(f"scored {count} job(s)")
    return count


def cmd_score(args) -> None:
    run_score(args.limit)


def run_report(log=print) -> str:
    from . import config, digest

    cfgd = config.load_config()
    report = cfgd.get("report") or {}
    path, _ = digest.build_report(_db(), int(report.get("top_n", 15)), int(report.get("min_score", 50)),
                                  max_age_days=int(cfgd.get("max_age_days", 3)))
    log(f"report: {path}")
    return str(path)


def cmd_report(args) -> None:
    run_report()


def cmd_jobs(args) -> None:
    db = _db()
    jobs = db.by_state(args.state) if args.state else db.all()
    jobs = sorted(jobs, key=lambda j: j.get("score") or 0, reverse=True)[:args.limit]
    for job in jobs:
        print(f"{job['id']}  {str(job.get('score') or '-'):>3}  {job['state']:<11} {job.get('company')}: "
              f"{job.get('title')}")
    if args.json:
        _print_json(jobs)


def cmd_set_state(args) -> None:
    db = _db()
    state = {"approve": "approved", "reject": "rejected"}.get(args.command, getattr(args, "state", None))
    for job_id in args.ids:
        try:
            db.set_state(job_id, state)
            print(f"{job_id} -> {state}")
        except (KeyError, ValueError) as exc:
            print(f"{job_id}: {exc}")


# ------------------------------------------------------------------ applications

def _gate_output(outcome: dict) -> None:
    print(f"RESULT: {outcome['result']}")
    details = {k: v for k, v in outcome.items() if k not in ("result", "next", "ok", "prompt", "status")}
    if details:
        _print_json(details)
    print(f"NEXT: {outcome['next']}")
    if not outcome.get("ok"):
        raise SystemExit(1)


def cmd_app(args) -> None:
    from .writer import gates, kit

    db = _db()
    if args.action == "prepare":
        job = db.get(args.ref)
        if job is None:
            raise SystemExit(f"unknown job id {args.ref!r}; see `jobauto jobs`")
        if job["state"] in ("discovered", "scored"):
            if not args.approve:
                raise SystemExit(f"{args.ref} is {job['state']}: approve it first (`jobauto approve {args.ref}`) "
                                 "or pass --approve")
            db.set_state(job["id"], "approved")
            job = db.get(args.ref)
        prepared = kit.prepare(job, redo=args.redo)
        for warning in prepared["warnings"]:
            print(f"warning: {warning}")
        print(f"application folder: {prepared['app_dir']}")
        print(f"prompt: {prepared['prompt_path']}")
        print("Paste PROMPT.md into your coding agent (Claude Code, Codex, Cursor, Gemini CLI, ...).")
        return
    if args.action == "status":
        _print_json(gates.summary(args.ref))
        return
    gate = {"check-plan": gates.check_plan, "render": gates.render, "finalize": gates.finalize}[args.action]
    _gate_output(gate(args.ref, db))


def cmd_autopilot(args) -> None:
    from .writer import autopilot, kit
    from .writer.agents import claude_available, runner_from_config

    if args.fetch:
        try:
            run_fetch()
            run_score()
        except Exception as exc:  # discovery trouble must not block writing approved jobs
            print(f"discovery failed, continuing with approved jobs: {type(exc).__name__}: {exc}")
    settings = kit.settings_from_config()
    if args.template:
        settings["templates"] = [t for t in args.template.split(",") if t]
    runner = runner_from_config(settings)
    if args.model:
        runner.model = args.model
    if not claude_available(runner.command):
        raise SystemExit(f"{runner.command!r} is not on PATH. Use `jobauto app prepare <id>` and paste PROMPT.md "
                         "into your agent instead.")
    results = autopilot.run(_db(), runner, settings, job_ids=args.ids or None, max_jobs=args.max_jobs,
                            redo=args.redo)
    for r in results:
        print(f"{r.get('result', '?'):>16}  {r.get('company')}  ${float(r.get('cost_usd') or 0):.2f}  "
              f"{r.get('application_dir', '')}")
    if any(r.get("result") not in kit.TERMINAL for r in results):
        raise SystemExit(1)


def cmd_templates(args) -> None:
    from .writer import rendercv_engine, themes
    from .writer.render import render_suite

    content = json.loads(Path(args.content).read_text(encoding="utf-8"))
    job = json.loads(Path(args.job).read_text(encoding="utf-8")) if args.job else content.get("job", {})
    out = Path(args.out) if args.out else Path(args.content).parent / "template-gallery"
    report = render_suite(content, job, out, html_themes=list(themes.THEMES),
                          rendercv_themes=list(rendercv_engine.DEFAULT_THEMES), allow_errors=True)
    for t in report["templates"]:
        print(f"{'ok' if t.get('ok') else 'check':>6}  {t['engine']}-{t['theme']}  {t.get('error', '')}")
    print(f"gallery: {out / 'gallery.html'}")


def cmd_serve(args) -> None:
    import threading
    import time
    import webbrowser

    import uvicorn

    url = f"http://127.0.0.1:{args.port}"
    if args.open:
        threading.Thread(target=lambda: (time.sleep(1.5), webbrowser.open(url)), daemon=True).start()
    print(f"dashboard: {url}")
    uvicorn.run("jobauto.dashboard:app", host="127.0.0.1", port=args.port, log_level="warning")


# ----------------------------------------------------------------------- parser

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jobauto", description="Job discovery and agent-written applications.")
    parser.add_argument("--home", help="project folder (default: the checkout or the current folder)")
    sub = parser.add_subparsers(dest="command", required=True)

    sp = sub.add_parser("init", help="create your private profile files")
    sp.add_argument("--force", action="store_true", help="overwrite existing files with the examples")
    sp.set_defaults(func=cmd_init)
    sub.add_parser("doctor", help="check this machine").set_defaults(func=cmd_doctor)
    sub.add_parser("fetch", help="discover postings").set_defaults(func=cmd_fetch)
    sp = sub.add_parser("score", help="rank unscored postings")
    sp.add_argument("--limit", type=int, default=500)
    sp.set_defaults(func=cmd_score)
    sub.add_parser("report", help="write today's digest").set_defaults(func=cmd_report)
    sp = sub.add_parser("jobs", help="list jobs")
    sp.add_argument("--state")
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--json", action="store_true")
    sp.set_defaults(func=cmd_jobs)
    for name in ("approve", "reject"):
        sp = sub.add_parser(name, help=f"{name} jobs")
        sp.add_argument("ids", nargs="+")
        sp.set_defaults(func=cmd_set_state)
    sp = sub.add_parser("set-state", help="move jobs to any legal state (e.g. applied)")
    sp.add_argument("state")
    sp.add_argument("ids", nargs="+")
    sp.set_defaults(func=cmd_set_state)

    sp = sub.add_parser("app", help="application kit and gates")
    sp.add_argument("action", choices=["prepare", "check-plan", "render", "finalize", "status"])
    sp.add_argument("ref", help="job id (prepare) or application folder / job id (gates)")
    sp.add_argument("--redo", action="store_true", help="prepare: start the application over")
    sp.add_argument("--approve", action="store_true", help="prepare: approve a scored job first")
    sp.set_defaults(func=cmd_app)

    sp = sub.add_parser("autopilot", help="write approved applications with the Claude CLI")
    sp.add_argument("ids", nargs="*")
    sp.add_argument("--max-jobs", type=int, default=1)
    sp.add_argument("--redo", action="store_true")
    sp.add_argument("--fetch", action="store_true", help="fetch and score before writing")
    sp.add_argument("--template", help="comma-separated, e.g. rendercv-sb2nov")
    sp.add_argument("--model")
    sp.set_defaults(func=cmd_autopilot)

    sp = sub.add_parser("templates", help="render a content.json in every template to compare them")
    sp.add_argument("content")
    sp.add_argument("--job")
    sp.add_argument("--out")
    sp.set_defaults(func=cmd_templates)

    sp = sub.add_parser("serve", help="open the dashboard")
    sp.add_argument("--port", type=int, default=8000)
    sp.add_argument("--open", action="store_true")
    sp.set_defaults(func=cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.home:
        os.environ["JOBAUTO_HOME"] = str(Path(args.home).expanduser().resolve())
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args.func(args)


if __name__ == "__main__":
    main()
