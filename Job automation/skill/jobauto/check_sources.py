"""Reachability + token validity check for every configured source.

For each company in companies.yml and each aggregator in config.yml it makes the real
HTTP request and reports:
  OK <n jobs>  — endpoint reachable AND the token returns parseable postings
  HTTP 200/0   — reachable but no postings parsed (token may be wrong, or empty board)
  AUTH 401/403 — blocked or needs API keys (e.g. Adzuna, or anti-bot)
  NOTFOUND 404 — wrong token / board does not exist
  ERR          — connection/timeout/DNS error

IMPORTANT: must run where outbound HTTP works (OpenClaw or your machine). A locked-down
sandbox will report everything as ERR/AUTH — that is the environment, not the config.
"""
from __future__ import annotations

import json
from typing import Any

from . import config as cfg
from .config import output_dir
from .sources import build_recipes, parse, Recipe
from .sources.aggregators import build_aggregator_recipes, parse_aggregator


def _client(timeout: float):
    import httpx
    return httpx.Client(timeout=timeout, follow_redirects=True,
                        headers={"User-Agent": "jobauto-check/0.1"})


def _classify(status: int, n: int | None) -> str:
    if status == 200:
        return f"OK ({n} jobs)" if n else "HTTP 200 (no jobs parsed)"
    if status in (401, 403):
        return f"AUTH {status} (blocked / needs key)"
    if status == 404:
        return f"NOTFOUND 404 (bad token?)"
    return f"HTTP {status}"


def _check_one(client, r: Recipe, kind: str) -> dict:
    res = {"name": r.company, "portal": r.portal, "method": r.method, "url": r.list_url}
    try:
        if r.method == "POST":
            resp = client.post(r.list_url, json=r.body or {}, headers=r.headers)
        else:
            resp = client.get(r.list_url, headers=r.headers)
        n = None
        if resp.status_code == 200:
            try:
                payload = resp.json()
                postings = (parse_aggregator(r, payload, cfg.load_config().get("include_keywords", []))
                            if kind == "agg" else parse(r, payload))
                n = len(postings)
            except Exception:
                n = None
        res["status"] = _classify(resp.status_code, n)
        res["ok"] = resp.status_code == 200
        res["jobs"] = n
    except Exception as e:
        res["status"] = f"ERR ({type(e).__name__})"
        res["ok"] = False
        res["jobs"] = None
        res["note"] = str(e)[:90]
    return res


def check_all(timeout: float = 15.0) -> list[dict]:
    company_recipes = build_recipes(cfg.load_companies())
    agg_recipes = build_aggregator_recipes(cfg.load_config(), cfg.load_secrets())
    out = []
    with _client(timeout) as client:
        for r in company_recipes:
            out.append(_check_one(client, r, "company"))
        for r in agg_recipes:
            out.append(_check_one(client, r, "agg"))
    return out


def run(timeout: float = 15.0) -> dict[str, Any]:
    results = check_all(timeout)
    ok = [r for r in results if r.get("ok")]
    summary = {"total": len(results), "ok": len(ok),
               "needs_attention": [r for r in results if not r.get("ok")]}
    path = output_dir() / "source_check.json"
    path.write_text(json.dumps({"summary": {"total": len(results), "ok": len(ok)},
                                "results": results}, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    return {"results": results, "ok": len(ok), "total": len(results), "path": str(path)}
