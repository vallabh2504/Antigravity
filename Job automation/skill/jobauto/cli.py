"""Command-line entrypoint. The agent drives the workflow through these commands.

Typical agent-backend run (this container, or OpenClaw):
  1. python -m jobauto manifest          # what to fetch
  2. <agent fetches those URLs with web/browser tools, writes raw.json>
  3. python -m jobauto ingest raw.json    # normalize + dedupe + store
  4. python -m jobauto to-score           # emit jobs to LLM-score
  5. <agent scores, writes scores.json>
  6. python -m jobauto apply-scores scores.json
  7. python -m jobauto report             # build the daily digest
  8. (after human approves) to-tailor -> apply-tailor -> prefill

httpx backend (OpenClaw on an unblocked host) collapses 1-3 into:
  python -m jobauto fetch
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as cfg
from .db import DB
from .models import RawPosting
from .normalize import ingest as do_ingest
import yaml

from .sources import build_recipes
from .sources.fetch import fetch_all, manifest as build_manifest
from .sources.aggregators import build_aggregator_recipes
from .sources.websearch import build_search_plan
from . import discover as discovery
from . import score as scoring
from . import tailor as tailoring
from . import digest as digesting
from . import apply_prefill as prefilling


def _db() -> DB:
    return DB(cfg.db_path())


def _write_json(name: str, data) -> Path:
    p = cfg.output_dir() / name
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return p


def _read_json(path: str):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _all_recipes():
    return (build_recipes(cfg.load_companies())
            + build_aggregator_recipes(cfg.load_config(), cfg.load_secrets()))


def cmd_manifest(args):
    man = build_manifest(_all_recipes())
    p = _write_json("manifest.json", man)
    print(f"{len(man)} source requests ({len(cfg.load_companies())} companies + aggregators) -> {p}")
    for m in man:
        print(f"  [{m['portal']}] {m['company']}: {m['method']} {m['url']}")


def cmd_fetch(args):
    raws = fetch_all(_all_recipes())
    res = do_ingest(_db(), raws)
    print(f"fetched {len(raws)} postings -> new={res['new']} dup={res['dup']}")


def cmd_search_plan(args):
    plan = build_search_plan(cfg.load_companies(), cfg.load_config())
    qs = plan["queries"]
    if args.limit:
        qs = qs[:args.limit]
        plan["queries"] = qs
    p = _write_json("search_plan.json", plan)
    print(f"{len(qs)} WebSearch queries (claude backend) -> {p}")
    for q in qs[:12]:
        print(f"  [{q['kind']}] {q['query']}")
    if len(qs) > 12:
        print(f"  ... +{len(qs) - 12} more")


def cmd_discover_sources(args):
    task = discovery.build_discovery_queries(
        cfg.load_config().get("include_keywords", []),
        cfg.load_config().get("locations", []))
    p = _write_json("discover_queries.json", task)
    print(f"{len(task['queries'])} discovery searches -> {p}")
    print("Run these with web tools, map ATS URLs via discover.url_to_company,")
    print("then: python -m jobauto add-companies new_companies.json")


def cmd_add_companies(args):
    new = _read_json(args.file)
    path = cfg.SKILL_DIR / "companies.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {"companies": []}
    existing = data.get("companies", [])
    have = {(c.get("name", "").lower(), c.get("token", "")) for c in existing}
    added = 0
    for c in new:
        key = (c.get("name", "").lower(), c.get("token", ""))
        if key in have or not c.get("name"):
            continue
        existing.append(c)
        have.add(key)
        added += 1
    data["companies"] = existing
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    print(f"added {added} new companies -> {path} (total {len(existing)})")


def cmd_ingest(args):
    data = _read_json(args.file)
    raws = [RawPosting(
        source=d.get("source", f"agent:{d.get('company','')}"),
        company=d.get("company", ""), title=d.get("title", ""),
        location=d.get("location", ""), url=d.get("url", ""),
        jd_text=d.get("jd_text", ""), posted_at=d.get("posted_at", ""),
        extra=d.get("extra", {}),
    ) for d in data]
    res = do_ingest(_db(), raws)
    print(f"ingested {len(raws)} -> new={res['new']} dup={res['dup']}")


def cmd_to_score(args):
    task = scoring.build_score_tasks(_db(), cfg.load_config(), cfg.load_profile(), args.limit)
    p = _write_json("to_score.json", task)
    print(f"{len(task['jobs'])} jobs to score, {len(task['dropped_by_rules'])} dropped by rules -> {p}")


def cmd_apply_scores(args):
    n = scoring.apply_scores(_db(), _read_json(args.file))
    print(f"applied {n} scores")


def cmd_to_tailor(args):
    task = tailoring.build_tailor_tasks(_db(), cfg.load_profile(), cfg.load_master_resume())
    p = _write_json("to_tailor.json", task)
    print(f"{len(task['jobs'])} jobs to tailor -> {p}")


def cmd_apply_tailor(args):
    n = tailoring.apply_tailor(_db(), _read_json(args.file))
    print(f"wrote tailored docs for {n} jobs -> {cfg.output_dir()}")


def cmd_to_prefill(args):
    applicant = cfg.load_secrets().get("applicant", {})
    task = prefilling.build_prefill_tasks(_db(), applicant)
    p = _write_json("to_prefill.json", task)
    print(f"{len(task['jobs'])} jobs to pre-fill -> {p}")


def cmd_set_state(args):
    db = _db()
    for jid in args.ids:
        if db.get(jid):
            db.set_state(jid, args.state)
            print(f"{jid} -> {args.state}")
        else:
            print(f"{jid} not found")


def cmd_report(args):
    path, _ = digesting.build_report(_db(), args.top_n, args.min_score)
    print(f"report -> {path}")


def cmd_stats(args):
    print(json.dumps(_db().counts(), indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jobauto", description="OpenClaw job automation pipeline")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("manifest").set_defaults(func=cmd_manifest)
    sub.add_parser("fetch").set_defaults(func=cmd_fetch)
    sp = sub.add_parser("search-plan"); sp.add_argument("--limit", type=int, default=0)
    sp.set_defaults(func=cmd_search_plan)
    sub.add_parser("discover-sources").set_defaults(func=cmd_discover_sources)
    sp = sub.add_parser("add-companies"); sp.add_argument("file")
    sp.set_defaults(func=cmd_add_companies)

    sp = sub.add_parser("ingest"); sp.add_argument("file"); sp.set_defaults(func=cmd_ingest)

    sp = sub.add_parser("to-score"); sp.add_argument("--limit", type=int, default=50)
    sp.set_defaults(func=cmd_to_score)

    sp = sub.add_parser("apply-scores"); sp.add_argument("file"); sp.set_defaults(func=cmd_apply_scores)

    sub.add_parser("to-tailor").set_defaults(func=cmd_to_tailor)
    sp = sub.add_parser("apply-tailor"); sp.add_argument("file"); sp.set_defaults(func=cmd_apply_tailor)

    sub.add_parser("to-prefill").set_defaults(func=cmd_to_prefill)

    for name, state in (("approve", "approved"), ("reject", "rejected")):
        sp = sub.add_parser(name); sp.add_argument("ids", nargs="+")
        sp.set_defaults(func=cmd_set_state, state=state)
    sp = sub.add_parser("set-state"); sp.add_argument("state"); sp.add_argument("ids", nargs="+")
    sp.set_defaults(func=cmd_set_state)

    sp = sub.add_parser("report"); sp.add_argument("--top-n", type=int, default=15)
    sp.add_argument("--min-score", type=int, default=50); sp.set_defaults(func=cmd_report)

    sub.add_parser("stats").set_defaults(func=cmd_stats)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main(sys.argv[1:])
