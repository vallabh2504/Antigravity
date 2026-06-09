"""Local visual dashboard for the job-automation pipeline (localhost only).

Run:
    pip install fastapi uvicorn python-multipart
    cd "Job automation"
    python -m uvicorn dashboard.app:app --reload --port 8000
    # open http://localhost:8000

Reads/writes the same output/jobs.db, so approvals stay in sync with the CLI.
No external assets, no Vercel — everything is inline so it runs offline.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, PlainTextResponse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skill"))
from jobauto import config as cfg          # noqa: E402
from jobauto.db import DB                  # noqa: E402

app = FastAPI(title="Job Automation Dashboard")

ACCENT = "#0b6e4f"
STATE_COLORS = {
    "discovered": "#8a94a6", "scored": "#2563eb", "approved": "#0b6e4f",
    "rejected": "#b42318", "docs_ready": "#7c3aed", "prefilled": "#b45309",
    "applied": "#0891b2", "screen": "#0891b2", "onsite": "#0891b2",
    "offer": "#0b6e4f", "closed": "#8a94a6",
}

CSS = f"""
*{{box-sizing:border-box}} :root{{--accent:{ACCENT}}}
body{{margin:0;font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
  background:#f4f6f8;color:#0f172a;line-height:1.5}}
a{{color:#2563eb;text-decoration:none}} a:hover{{text-decoration:underline}}
.wrap{{max-width:1040px;margin:0 auto;padding:0 18px 48px}}
header.top{{background:linear-gradient(120deg,#0b6e4f,#0e8a63);color:#fff;padding:22px 0 18px;margin-bottom:18px;
  box-shadow:0 2px 10px rgba(0,0,0,.08)}}
header.top .wrap{{padding-bottom:0}}
header.top h1{{margin:0;font-size:22px;letter-spacing:.3px}}
header.top .sub{{opacity:.9;font-size:13px;margin-top:3px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap;margin:16px 0 6px}}
.card{{background:#fff;border:1px solid #e6eaef;border-radius:12px;padding:12px 16px;min-width:104px;
  box-shadow:0 1px 2px rgba(16,24,40,.04)}}
.card .n{{font-size:24px;font-weight:700}} .card .l{{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:#64748b}}
.tabs{{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}}
.tab{{background:#fff;border:1px solid #e6eaef;border-radius:999px;padding:6px 14px;font-size:13px;color:#334155}}
.tab.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.job{{background:#fff;border:1px solid #e6eaef;border-radius:14px;padding:16px 18px;margin:0 0 14px;
  box-shadow:0 1px 3px rgba(16,24,40,.05);display:flex;gap:16px}}
.rank{{font-size:13px;color:#94a3b8;font-weight:700;min-width:22px}}
.scorebadge{{min-width:54px;height:54px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-weight:700;font-size:17px;color:#fff;flex:0 0 auto}}
.jobmain{{flex:1}}
.jobmain h3{{margin:0 0 2px;font-size:16.5px}} .co{{color:#475569;font-size:13.5px}}
.tags{{margin:8px 0 6px;display:flex;gap:6px;flex-wrap:wrap}}
.tag{{background:#eef2f6;border-radius:6px;padding:2px 9px;font-size:12px;color:#475569}}
.tag.phd{{background:#f3e8ff;color:#7c3aed}} .tag.de{{background:#fff7ed;color:#b45309}}
.tag.sector{{background:#ecfdf5;color:#0b6e4f}}
.pill{{border-radius:6px;padding:2px 9px;color:#fff;font-size:11.5px;font-weight:600}}
ul.reasons{{margin:6px 0 10px;padding-left:18px;color:#334155;font-size:13.5px}} ul.reasons li{{margin:2px 0}}
.acts{{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:4px}}
button{{cursor:pointer;border:0;border-radius:8px;padding:7px 14px;font-size:13px;color:#fff;font-weight:600}}
.ok{{background:#0b6e4f}} .no{{background:#b42318}} .ghost{{background:#fff;color:#334155;border:1px solid #d6dde6}}
.docbtn{{background:#2563eb}}
.detail{{display:grid;grid-template-columns:1fr 360px;gap:18px}}
@media(max-width:820px){{.detail{{grid-template-columns:1fr}}}}
.panel{{background:#fff;border:1px solid #e6eaef;border-radius:14px;padding:16px 18px}}
pre.jd{{white-space:pre-wrap;font-family:inherit;font-size:13.5px;color:#1f2937;margin:0;max-height:560px;overflow:auto}}
.back{{color:#fff;opacity:.95;font-size:13px}}
.empty{{background:#fff;border:1px dashed #cbd5e1;border-radius:14px;padding:34px;text-align:center;color:#64748b}}
"""


def _db() -> DB:
    return DB(cfg.db_path())


def _score_color(s: int | None) -> str:
    s = s or 0
    if s >= 85: return "#0b6e4f"
    if s >= 70: return "#2563eb"
    if s >= 50: return "#b45309"
    return "#94a3b8"


def _page(title: str, body: str, sub: str = "") -> str:
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title>
<style>{CSS}</style></head><body>
<header class="top"><div class="wrap"><h1>⚡ Fuel-Cell Job Automation</h1>
<div class="sub">{sub or 'Local dashboard · localhost'}</div></div></header>
<div class="wrap">{body}</div></body></html>"""


def _stat_cards(counts: dict) -> str:
    order = ["discovered", "scored", "docs_ready", "approved", "prefilled", "applied"]
    cards = []
    for k in order:
        if counts.get(k):
            cards.append(f'<div class="card"><div class="n">{counts[k]}</div><div class="l">{k.replace("_"," ")}</div></div>')
    total = sum(counts.values())
    cards.insert(0, f'<div class="card"><div class="n">{total}</div><div class="l">total</div></div>')
    return f'<div class="cards">{"".join(cards)}</div>'


def _tabs(active: str) -> str:
    items = [("Review queue", "/"), ("All", "/all"), ("Docs ready", "/state/docs_ready"),
             ("Approved", "/state/approved"), ("Applied", "/state/applied")]
    out = []
    for label, href in items:
        cls = "tab active" if href == active else "tab"
        out.append(f'<a class="{cls}" href="{href}">{label}</a>')
    return f'<div class="tabs">{"".join(out)}</div>'


def _has_docs(job_id: str) -> bool:
    return (cfg.output_dir() / job_id / "cover_letter.html").exists()


def _job_card(j: dict, rank: int | None = None, actions: bool = True) -> str:
    sj = j.get("score_json") or {}
    tags = []
    if sj.get("sector"): tags.append(f'<span class="tag sector">{html.escape(sj["sector"])}</span>')
    if sj.get("is_phd"): tags.append('<span class="tag phd">PhD</span>')
    if sj.get("german_required"): tags.append(f'<span class="tag de">German {html.escape(sj["german_required"])}</span>')
    if sj.get("tier"): tags.append(f'<span class="tag">tier {html.escape(sj["tier"])}</span>')
    reasons = "".join(f"<li>{html.escape(str(r))}</li>" for r in (sj.get("reasons") or [])[:4])
    color = STATE_COLORS.get(j["state"], "#8a94a6")
    rankhtml = f'<div class="rank">#{rank}</div>' if rank else '<div class="rank"></div>'
    docbtns = ""
    if _has_docs(j["id"]):
        docbtns = (f'<a href="/doc/{j["id"]}/resume.html" target="_blank"><button class="docbtn">Résumé</button></a>'
                   f'<a href="/doc/{j["id"]}/cover_letter.html" target="_blank"><button class="docbtn">Cover letter</button></a>')
    acts = ""
    if actions:
        acts = f"""<form method="post" action="/action" style="display:inline">
          <input type="hidden" name="job_id" value="{j['id']}">
          <button class="ok" name="state" value="approved">✓ Approve</button>
          <button class="no" name="state" value="rejected">✕ Reject</button></form>"""
    return f"""<div class="job">
      {rankhtml}
      <div class="scorebadge" style="background:{_score_color(j.get('score'))}">{j.get('score','?')}</div>
      <div class="jobmain">
        <h3>{html.escape(j['title'])}</h3>
        <div class="co">{html.escape(j['company'])} · {html.escape(j.get('location') or 'location n/a')}
          <span class="pill" style="background:{color}">{j['state']}</span></div>
        <div class="tags">{''.join(tags)}</div>
        <ul class="reasons">{reasons}</ul>
        <div class="acts">
          <a href="{html.escape(j.get('url') or '#')}" target="_blank"><button class="ghost">Open posting ↗</button></a>
          <a href="/job/{j['id']}"><button class="ghost">Details</button></a>
          {docbtns}{acts}
        </div>
      </div></div>"""


def _next_banner(counts: dict) -> str:
    g = lambda k: counts.get(k, 0)
    if sum(counts.values()) == 0:
        msg = "Run discovery → scoring (CLI: <code>search-plan</code> / <code>fetch</code>)."
    elif g("discovered"):
        msg = f"<b>{g('discovered')}</b> new jobs to score — CLI: <code>to-score</code> → <code>apply-scores</code>."
    elif g("scored") and not g("docs_ready"):
        msg = "Write the top-3 applications — CLI: <code>to-apply</code> → application-writer → <code>apply-tailor</code>."
    elif g("docs_ready"):
        msg = f"<b>{g('docs_ready')}</b> drafted — review below, approve, then pre-fill (stops at submit)."
    elif g("prefilled"):
        msg = f"<b>{g('prefilled')}</b> pre-filled — review &amp; submit, then mark applied."
    else:
        msg = "Pipeline idle."
    return (f'<div class="panel" style="border-left:4px solid var(--accent);margin:0 0 16px">'
            f'<b style="color:var(--accent)">Next:</b> {msg}</div>')


def _filter_bar(q: str, min_score: int, sector: str, phd: bool) -> str:
    sectors = ["", "aviation", "rail", "heavy", "other"]
    opts = "".join(f'<option value="{s}"{" selected" if s==sector else ""}>{s or "all sectors"}</option>' for s in sectors)
    return f"""<form method="get" action="/" class="panel" style="display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 16px">
      <input name="q" value="{html.escape(q)}" placeholder="search company / title"
        style="flex:1;min-width:180px;padding:8px 10px;border:1px solid #d6dde6;border-radius:8px;font-size:14px">
      <label style="font-size:13px;color:#475569">min score
        <input name="min_score" type="number" value="{min_score}" min="0" max="100" style="width:64px;padding:7px;border:1px solid #d6dde6;border-radius:8px"></label>
      <select name="sector" style="padding:8px;border:1px solid #d6dde6;border-radius:8px">{opts}</select>
      <label style="font-size:13px;color:#475569"><input type="checkbox" name="phd" value="1"{" checked" if phd else ""}> PhD only</label>
      <button class="docbtn" type="submit">Filter</button>
      <a href="/" style="font-size:13px">reset</a>
    </form>"""


@app.get("/", response_class=HTMLResponse)
def index(q: str = "", min_score: int = 0, sector: str = "", phd: str = ""):
    db = _db()
    counts = db.counts()
    phd_only = phd in ("1", "true", "on")
    jobs = [j for j in db.all() if j.get("score") is not None and j["state"] in ("scored", "approved", "docs_ready")]
    ql = q.lower().strip()
    def keep(j):
        sj = j.get("score_json") or {}
        if ql and ql not in (j["company"] + " " + j["title"]).lower(): return False
        if (j.get("score") or 0) < min_score: return False
        if sector and sj.get("sector") != sector: return False
        if phd_only and not sj.get("is_phd"): return False
        return True
    jobs = [j for j in jobs if keep(j)]
    jobs.sort(key=lambda j: j.get("score") or 0, reverse=True)
    cards = "".join(_job_card(j, rank=i) for i, j in enumerate(jobs, 1)) or \
        '<div class="empty">No jobs match the filters.</div>'
    body = (_stat_cards(counts) + _tabs("/") + _next_banner(counts)
            + _filter_bar(q, min_score, sector, phd_only)
            + f"<h2>Review queue · {len(jobs)} shown</h2>" + cards)
    return _page("Job Automation", body, "Review queue · filter, review, approve")


@app.get("/all", response_class=HTMLResponse)
def all_jobs():
    db = _db()
    jobs = sorted(db.all(), key=lambda j: j.get("score") or -1, reverse=True)
    cards = "".join(_job_card(j) for j in jobs) or '<div class="empty">No jobs.</div>'
    return _page("All jobs", _stat_cards(db.counts()) + _tabs("/all") + "<h2>All jobs</h2>" + cards)


@app.get("/state/{state}", response_class=HTMLResponse)
def by_state(state: str):
    db = _db()
    cards = "".join(_job_card(j, actions=False) for j in db.by_state(state)) or \
        f'<div class="empty">Nothing in “{html.escape(state)}”.</div>'
    return _page(state, _stat_cards(db.counts()) + _tabs(f"/state/{state}") + f"<h2>{html.escape(state)}</h2>" + cards)


@app.get("/job/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: str):
    db = _db()
    j = db.get(job_id)
    if not j:
        return _page("Not found", '<div class="empty">Not found. <a href="/">back</a></div>')
    jd = html.escape(j.get("jd_text") or "(no job description captured)")
    docs_dir = cfg.output_dir() / job_id
    right = ""
    if _has_docs(job_id):
        why = docs_dir / "why_fit.md"
        whytxt = html.escape(why.read_text(encoding="utf-8")) if why.exists() else ""
        right = f"""<div class="panel">
          <h3>Tailored documents</h3>
          <div class="acts" style="margin-bottom:10px">
            <a href="/doc/{job_id}/resume.html" target="_blank"><button class="docbtn">Open résumé</button></a>
            <a href="/doc/{job_id}/cover_letter.html" target="_blank"><button class="docbtn">Open cover letter</button></a>
          </div>
          <pre class="jd" style="max-height:none">{whytxt}</pre></div>"""
    else:
        right = '<div class="panel"><h3>Tailored documents</h3><p style="color:#64748b">Not generated yet (top-3 only).</p></div>'
    preview = ""
    if _has_docs(job_id):
        preview = f"""<h2 style="margin-top:22px">Document preview</h2>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
          <div><div style="font-weight:600;margin-bottom:6px">Résumé</div>
            <iframe src="/doc/{job_id}/resume.html" style="width:100%;height:920px;border:1px solid #e6eaef;border-radius:12px;background:#fff"></iframe></div>
          <div><div style="font-weight:600;margin-bottom:6px">Cover letter</div>
            <iframe src="/doc/{job_id}/cover_letter.html" style="width:100%;height:920px;border:1px solid #e6eaef;border-radius:12px;background:#fff"></iframe></div>
        </div>"""
    body = f"""<a class="back" href="/">← back to queue</a>
      {_job_card(j)}
      <div class="detail">
        <div class="panel"><h3>Job description</h3><pre class="jd">{jd}</pre></div>
        {right}
      </div>
      {preview}"""
    return _page(j["title"], body, f"{j['company']} · {j.get('location') or ''}")


@app.get("/doc/{job_id}/{which}")
def doc(job_id: str, which: str):
    if which not in ("resume.html", "cover_letter.html", "resume.md", "cover_letter.md"):
        return PlainTextResponse("not allowed", status_code=400)
    p = cfg.output_dir() / job_id / which
    if not p.exists():
        return PlainTextResponse("not found", status_code=404)
    media = "text/html" if which.endswith(".html") else "text/plain"
    return FileResponse(str(p), media_type=media)


@app.post("/action")
def action(job_id: str = Form(...), state: str = Form(...)):
    _db().set_state(job_id, state)
    return RedirectResponse("/", status_code=303)
