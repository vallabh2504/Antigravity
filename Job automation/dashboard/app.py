"""Web dashboard for the job-automation pipeline.

Agent-agnostic: reads the same output/jobs.db and lets you browse ranked jobs,
approve/reject (writes state back), and view tailored docs. Run locally:

    pip install fastapi uvicorn
    uvicorn dashboard.app:app --reload --port 8000   # from the "Job automation" dir

Then open http://localhost:8000 . Deploy to Vercel is possible but read-only
(serverless filesystem is ephemeral) — local is the intended use for approvals.
"""
from __future__ import annotations

import html
import sys
from pathlib import Path

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

# make the skill package importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "skill"))
from jobauto import config as cfg          # noqa: E402
from jobauto.db import DB                  # noqa: E402

app = FastAPI(title="Job Automation Dashboard")

STATE_COLORS = {
    "discovered": "#888", "scored": "#0969da", "approved": "#1a7f37",
    "rejected": "#b00", "docs_ready": "#8250df", "prefilled": "#bf8700",
    "applied": "#0a7", "screen": "#0a7", "onsite": "#0a7", "offer": "#1a7f37",
    "closed": "#888",
}


def _db() -> DB:
    return DB(cfg.db_path())


def _page(body: str) -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
    <title>Job Automation</title><meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
      body{{font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:900px;margin:24px auto;padding:0 14px;color:#111}}
      .job{{border:1px solid #e3e3e3;border-radius:10px;padding:14px 16px;margin:0 0 14px}}
      .score{{color:#1a7f37;font-weight:600}} .muted{{color:#888;font-size:12px}}
      .tag{{display:inline-block;background:#f0f3f6;border-radius:6px;padding:1px 7px;margin-right:5px;font-size:12px;color:#444}}
      button{{cursor:pointer;border:0;border-radius:7px;padding:6px 12px;font-size:13px;color:#fff}}
      .ok{{background:#1a7f37}} .no{{background:#b00}} a{{color:#0969da;text-decoration:none}}
      ul{{margin:6px 0;padding-left:18px}} .pill{{border-radius:6px;padding:1px 8px;color:#fff;font-size:12px}}
    </style></head><body>{body}</body></html>"""


def _job_card(j: dict, show_actions: bool = True) -> str:
    sj = j.get("score_json") or {}
    tags = "".join(f'<span class="tag">{html.escape(str(t))}</span>' for t in filter(None, [
        sj.get("sector"), "PhD" if sj.get("is_phd") else "",
        f"DE:{sj['german_required']}" if sj.get("german_required") else "",
        f"tier {sj.get('tier')}" if sj.get("tier") else ""]))
    reasons = "".join(f"<li>{html.escape(str(r))}</li>" for r in (sj.get("reasons") or [])[:4])
    color = STATE_COLORS.get(j["state"], "#888")
    actions = ""
    if show_actions:
        actions = f"""
        <form method="post" action="/action" style="display:inline">
          <input type="hidden" name="job_id" value="{j['id']}">
          <button class="ok" name="state" value="approved">Approve</button>
          <button class="no" name="state" value="rejected">Reject</button>
        </form>"""
    return f"""<div class="job">
      <div style="font-size:16px"><b>{html.escape(j['title'])}</b> <span class="score">({j.get('score','?')}/100)</span></div>
      <div>{html.escape(j['company'])} — {html.escape(j.get('location') or 'n/a')}
        <span class="pill" style="background:{color}">{j['state']}</span></div>
      <div style="margin:5px 0">{tags}</div>
      <ul>{reasons}</ul>
      <a href="{html.escape(j.get('url') or '#')}" target="_blank">Open posting →</a>
      &nbsp; <a href="/job/{j['id']}">details</a>
      <div style="margin-top:8px">{actions}</div>
    </div>"""


@app.get("/", response_class=HTMLResponse)
def index():
    db = _db()
    counts = db.counts()
    bar = " · ".join(f'<b>{v}</b> {k}' for k, v in sorted(counts.items())) or "empty"
    jobs = [j for j in db.all() if j.get("score") is not None and j["state"] in ("scored", "approved")]
    cards = "".join(_job_card(j) for j in jobs) or "<p>No scored jobs yet. Run discovery + scoring.</p>"
    nav = '<p><a href="/all">all jobs</a> · <a href="/state/applied">applied</a> · <a href="/state/docs_ready">docs ready</a></p>'
    return _page(f"<h2>Job Automation</h2><p class='muted'>pipeline: {bar}</p>{nav}<h3>Review queue</h3>{cards}")


@app.get("/all", response_class=HTMLResponse)
def all_jobs():
    cards = "".join(_job_card(j) for j in _db().all())
    return _page(f"<h2><a href='/'>←</a> All jobs</h2>{cards or '<p>empty</p>'}")


@app.get("/state/{state}", response_class=HTMLResponse)
def by_state(state: str):
    cards = "".join(_job_card(j, show_actions=False) for j in _db().by_state(state))
    return _page(f"<h2><a href='/'>←</a> {html.escape(state)}</h2>{cards or '<p>none</p>'}")


@app.get("/job/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: str):
    db = _db()
    j = db.get(job_id)
    if not j:
        return _page("<p>Not found. <a href='/'>back</a></p>")
    jd = html.escape(j.get("jd_text") or "(no JD captured)")
    docs_dir = cfg.output_dir() / job_id
    docs = ""
    if docs_dir.exists():
        for name in ("cover_letter.md", "resume.md", "why_fit.md"):
            f = docs_dir / name
            if f.exists():
                docs += f"<h4>{name}</h4><pre style='white-space:pre-wrap;background:#f6f8fa;padding:10px;border-radius:8px'>{html.escape(f.read_text(encoding='utf-8'))}</pre>"
    return _page(f"""<h2><a href='/'>←</a> {html.escape(j['title'])}</h2>
      <p>{html.escape(j['company'])} — {html.escape(j.get('location') or 'n/a')} ·
      <a href="{html.escape(j.get('url') or '#')}" target="_blank">posting</a> · state {j['state']}</p>
      {_job_card(j)}
      <h3>Job description</h3><pre style='white-space:pre-wrap;background:#f6f8fa;padding:10px;border-radius:8px'>{jd}</pre>
      {('<h3>Tailored documents</h3>' + docs) if docs else ''}""")


@app.post("/action")
def action(job_id: str = Form(...), state: str = Form(...)):
    _db().set_state(job_id, state)
    return RedirectResponse("/", status_code=303)
