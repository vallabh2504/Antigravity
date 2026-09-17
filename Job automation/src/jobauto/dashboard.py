"""Local dashboard: review jobs, prepare applications, follow their progress.

Start it with ``jobauto serve --open``.  It listens on 127.0.0.1 only.  Every
state-changing request carries a per-process token so another web page cannot
post to it.
"""
from __future__ import annotations

import secrets
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

from . import config
from .db import DB
from .writer import autopilot, gates, kit
from .writer.agents import claude_available, runner_from_config

app = FastAPI(title="jobauto")
TOKEN = secrets.token_urlsafe(24)
_lock = threading.Lock()
_task: dict[str, Any] = {"name": None, "running": False, "log": []}


def _db() -> DB:
    return DB(config.db_path())


def _check(token: str | None) -> None:
    if token != TOKEN:
        raise HTTPException(403, "missing or wrong X-Token header; reload the page")


def _app_summary(job_id: str) -> dict[str, Any] | None:
    folder = kit.find_by_job_id(job_id)
    return gates.summary(folder) if folder else None


class StateBody(BaseModel):
    state: str


class PrepareBody(BaseModel):
    redo: bool = False


class TaskBody(BaseModel):
    name: str
    job_id: str | None = None


@app.get("/api/jobs")
def jobs(state: str = "", q: str = "", min_score: int = 0, limit: int = 300) -> dict[str, Any]:
    db = _db()
    rows = db.by_state(state) if state else db.all()
    q = q.lower().strip()
    out = []
    for job in rows:
        if (job.get("score") or 0) < min_score:
            continue
        if q and q not in f"{job.get('company')} {job.get('title')} {job.get('location')}".lower():
            continue
        out.append({k: job.get(k) for k in ("id", "company", "title", "location", "url", "posted_at", "score",
                                            "state")} | {"has_application": kit.find_by_job_id(job["id"]) is not None})
    out.sort(key=lambda j: j.get("score") or 0, reverse=True)
    return {"jobs": out[:limit], "counts": db.counts(), "claude": claude_available(
        kit.settings_from_config()["agent"]["command"]), "problems": kit.candidate_problems()}


@app.get("/api/jobs/{job_id}")
def job_detail(job_id: str) -> dict[str, Any]:
    job = _db().get(job_id)
    if job is None:
        raise HTTPException(404, "unknown job")
    return {"job": job, "application": _app_summary(job_id)}


@app.post("/api/jobs/{job_id}/state")
def set_state(job_id: str, body: StateBody, x_token: str | None = Header(None)) -> dict[str, Any]:
    _check(x_token)
    try:
        _db().set_state(job_id, body.state)
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc))
    return {"ok": True}


@app.post("/api/jobs/{job_id}/prepare")
def prepare(job_id: str, body: PrepareBody, x_token: str | None = Header(None)) -> dict[str, Any]:
    _check(x_token)
    db = _db()
    job = db.get(job_id)
    if job is None:
        raise HTTPException(404, "unknown job")
    if job["state"] in ("discovered", "scored"):
        db.set_state(job_id, "approved")  # preparing an application is the approval
        job = db.get(job_id)
    elif job["state"] not in ("approved", "docs_review", "docs_ready"):
        raise HTTPException(400, f"job is {job['state']}; move it back to approved first")
    try:
        prepared = kit.prepare(job, redo=body.redo)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {"prompt": prepared["prompt"], "warnings": prepared["warnings"], "app_dir": prepared["app_dir"],
            "prompt_path": prepared["prompt_path"], "application": _app_summary(job_id)}


@app.get("/api/jobs/{job_id}/file")
def app_file(job_id: str, path: str) -> FileResponse:
    folder = kit.find_by_job_id(job_id)
    if folder is None:
        raise HTTPException(404, "no application")
    target = (folder / path).resolve()
    if not target.is_file() or not target.is_relative_to(folder.resolve()):
        raise HTTPException(404, "not found")
    return FileResponse(target)


def _run_task(name: str, job_id: str | None) -> None:
    from . import cli

    def log(line: str) -> None:
        _task["log"].append(str(line))
        del _task["log"][:-400]

    try:
        if name == "pipeline":
            try:
                cli.run_fetch(log)
            except Exception as exc:
                log(f"fetch failed: {type(exc).__name__}: {exc}")
            cli.run_score(log=log)
            cli.run_report(log)
        elif name == "autopilot":
            settings = kit.settings_from_config()
            autopilot.run(_db(), runner_from_config(settings), settings, job_ids=[job_id] if job_id else None,
                          log=log)
        log("done")
    except Exception as exc:
        log(f"error: {type(exc).__name__}: {exc}")
    finally:
        _task["running"] = False


@app.post("/api/tasks")
def start_task(body: TaskBody, x_token: str | None = Header(None)) -> dict[str, Any]:
    _check(x_token)
    if body.name not in ("pipeline", "autopilot"):
        raise HTTPException(400, "unknown task")
    with _lock:
        if _task["running"]:
            raise HTTPException(409, f"{_task['name']} is still running")
        _task.update(name=body.name, running=True, log=[])
    threading.Thread(target=_run_task, args=(body.name, body.job_id), daemon=True).start()
    return {"ok": True}


@app.get("/api/tasks")
def task_status() -> dict[str, Any]:
    return _task


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return PAGE.replace("__TOKEN__", TOKEN)


PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>jobauto</title>
<style>
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--mute:#667085;--line:#e3e6eb;--accent:#1f5eff;--ok:#127a3e;--warn:#9a6700;--bad:#b42318}
@media (prefers-color-scheme:dark){:root{--bg:#12151b;--card:#1a1e26;--ink:#e6e9ef;--mute:#98a2b3;--line:#2b303b;--accent:#6c9bff;--ok:#4ade80;--warn:#facc15;--bad:#f87171}}
*{box-sizing:border-box}body{margin:0;font:14px/1.45 system-ui,sans-serif;background:var(--bg);color:var(--ink)}
header{display:flex;gap:12px;align-items:center;padding:12px 16px;border-bottom:1px solid var(--line);background:var(--card);flex-wrap:wrap}
header h1{font-size:16px;margin:0 12px 0 0}button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:6px;padding:5px 10px;cursor:pointer}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}button:disabled{opacity:.5;cursor:default}
input,select{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:6px;background:var(--card);color:var(--ink)}
main{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.1fr);gap:16px;padding:16px}
@media (max-width:900px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px}.tabs button.on{border-color:var(--accent);color:var(--accent)}
table{width:100%;border-collapse:collapse}td{padding:7px 6px;border-top:1px solid var(--line);vertical-align:top}
tr.row{cursor:pointer}tr.row:hover,tr.sel{background:color-mix(in srgb,var(--accent) 8%,transparent)}
.score{font-weight:600;width:36px;text-align:right}.mute{color:var(--mute)}.pill{font-size:12px;border:1px solid var(--line);border-radius:10px;padding:0 7px;white-space:nowrap}
textarea{width:100%;min-height:260px;font:12px/1.4 ui-monospace,monospace;background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:8px}
.warn{color:var(--warn)}.bad{color:var(--bad)}.ok{color:var(--ok)}pre{white-space:pre-wrap;font-size:12px;max-height:220px;overflow:auto;background:var(--bg);padding:8px;border-radius:6px}
.jd{max-height:260px;overflow:auto;white-space:pre-wrap;font-size:13px;border-top:1px solid var(--line);margin-top:8px;padding-top:8px}
.actions{display:flex;gap:6px;flex-wrap:wrap;margin:10px 0}h2{font-size:15px;margin:0 0 4px}h3{font-size:13px;margin:14px 0 4px}
</style></head><body>
<header><h1>jobauto</h1>
<input id="q" placeholder="Search company, title, place" oninput="load()">
<label class="mute">min score <input id="min" type="number" value="0" style="width:64px" oninput="load()"></label>
<button onclick="runTask('pipeline')">Fetch, score, report</button>
<span id="task" class="mute"></span></header>
<div id="problems" class="warn" style="padding:0 16px"></div>
<main><section class="card"><div class="tabs" id="tabs"></div><table id="list"></table></section>
<section class="card" id="detail"><p class="mute">Select a job.</p></section></main>
<script>
const TOKEN="__TOKEN__";let state="scored",selected=null,claude=false,poll=null;
const STATES=["scored","approved","docs_review","docs_ready","applied","rejected",""];
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
async function api(url,body){const r=await fetch(url,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json","X-Token":TOKEN},body:JSON.stringify(body)});
 const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.detail||r.statusText);return d}
async function load(){const p=new URLSearchParams({state,q:document.getElementById("q").value,min_score:document.getElementById("min").value||0});
 const d=await api("/api/jobs?"+p);claude=d.claude;
 document.getElementById("problems").innerHTML=d.problems.map(x=>"Profile: "+esc(x)).join("<br>");
 document.getElementById("tabs").innerHTML=STATES.map(s=>`<button class="${s===state?"on":""}" onclick="state='${s}';load()">${s||"all"} <span class="mute">${s?(d.counts[s]||0):""}</span></button>`).join("");
 document.getElementById("list").innerHTML=d.jobs.map(j=>`<tr class="row ${j.id===selected?"sel":""}" onclick="show('${esc(j.id)}')"><td class="score">${j.score??"-"}</td>
 <td><b>${esc(j.company)}</b><br>${esc(j.title)}<br><span class="mute">${esc(j.location)} ${esc(j.posted_at)}</span></td>
 <td><span class="pill">${esc(j.state)}</span>${j.has_application?' <span class="pill">application</span>':""}</td></tr>`).join("")||'<tr><td class="mute">No jobs here. Run "Fetch, score, report".</td></tr>'}
async function setState(id,s){try{await api(`/api/jobs/${id}/state`,{state:s});await load();await show(id)}catch(e){alert(e.message)}}
function appHtml(a){if(!a)return"";const rev=(a.reviews||[]).map(r=>`<li>round ${r.round}: content ${r.content??"-"}, design ${r.design??"-"} ${r.passed?'<span class="ok">passed</span>':'<span class="bad">revise</span>'}</li>`).join("");
 const res=a.result?`<b class="${a.result==="docs_ready"?"ok":"warn"}">${esc(a.result)}</b>`:esc(a.stage);
 const pdfs=(a.final_pdfs||[]).map(p=>{const n=p.split(/[\\/]/).pop();return`<a target="_blank" href="/api/jobs/${esc(a.job_id)}/file?path=${encodeURIComponent("final/"+n)}">${esc(n)}</a>`}).join("<br>");
 const fit=a.fit?`<p>Fit: <b>${esc(a.fit.verdict)}</b> ${esc(a.fit.reason||"")}</p>`:"";
 const q=(a.questions||[]).length?`<h3>Questions only you can answer</h3><ul>${a.questions.map(x=>`<li>${esc(typeof x==="string"?x:x.question||JSON.stringify(x))}</li>`).join("")}</ul><p class="mute">Answer them in profile/writer_answers.md, then prepare again.</p>`:"";
 const holds=(a.hold_reasons||[]).length?`<p class="warn">On hold: ${a.hold_reasons.map(esc).join("; ")}</p>`:"";
 return`<h3>Application</h3><p>Status: ${res} (round ${a.round??"-"})</p>${fit}${holds}${rev?`<ul>${rev}</ul>`:""}${pdfs?`<h3>Final PDFs</h3>${pdfs}`:""}${q}
 <p class="mute">${esc(a.app_dir)}</p>`}
async function show(id){selected=id;const d=await api(`/api/jobs/${id}`);const j=d.job;
 const canPrep=["scored","discovered","approved","docs_review","docs_ready"].includes(j.state);
 document.getElementById("detail").innerHTML=`<h2>${esc(j.title)}</h2><div>${esc(j.company)} · ${esc(j.location)} · score ${j.score??"-"} · <span class="pill">${esc(j.state)}</span></div>
 <a href="${esc(j.url)}" target="_blank" rel="noopener">Open posting</a>
 <div class="actions">${canPrep?`<button class="primary" onclick="prep('${id}',false)">Prepare application</button>`:""}
 ${d.application?`<button onclick="prep('${id}',true)">Start over</button>`:""}
 ${claude&&d.application?`<button onclick="runTask('autopilot','${id}')">Run with Claude CLI</button>`:""}
 ${j.state!=="approved"&&["scored","discovered"].includes(j.state)?`<button onclick="setState('${id}','approved')">Approve</button>`:""}
 ${j.state!=="rejected"?`<button onclick="setState('${id}','rejected')">Reject</button>`:""}
 ${j.state==="docs_ready"?`<button onclick="setState('${id}','applied')">I applied</button>`:""}</div>
 <div id="prompt"></div><div id="app">${appHtml(d.application)}</div>
 <details><summary>Job description</summary><div class="jd">${esc(j.jd_text)}</div></details>`;
 load();clearInterval(poll);if(d.application&&!["docs_ready","hold","needs_operator"].includes(d.application.result))
  poll=setInterval(async()=>{if(selected!==id)return clearInterval(poll);const x=await api(`/api/jobs/${id}`);document.getElementById("app").innerHTML=appHtml(x.application)},5000)}
async function prep(id,redo){if(redo&&!confirm("Delete this application's rounds and start over?"))return;
 try{const d=await api(`/api/jobs/${id}/prepare`,{redo});await show(id);
 document.getElementById("prompt").innerHTML=`${d.warnings.map(w=>`<p class="warn">${esc(w)}</p>`).join("")}
 <h3>Paste this prompt into your agent</h3><p class="mute">Claude Code, Codex, Cursor, Gemini CLI or any agent that can run shell commands and read files. Saved as ${esc(d.prompt_path)}</p>
 <div class="actions"><button class="primary" onclick="copyPrompt(this)">Copy prompt</button></div><textarea id="prompttext" readonly>${esc(d.prompt)}</textarea>`}catch(e){alert(e.message)}}
async function copyPrompt(b){const t=document.getElementById("prompttext");try{await navigator.clipboard.writeText(t.value)}catch{t.select();document.execCommand("copy")}b.textContent="Copied";setTimeout(()=>b.textContent="Copy prompt",1500)}
async function runTask(name,job_id){try{await api("/api/tasks",{name,job_id});watchTask()}catch(e){alert(e.message)}}
async function watchTask(){const t=await api("/api/tasks");const el=document.getElementById("task");
 el.textContent=t.name?`${t.name}: ${t.running?"running":"finished"} · ${(t.log||[]).slice(-1)[0]||""}`:"";el.title=(t.log||[]).join("\n");
 if(t.running)setTimeout(watchTask,2000);else if(t.name){load();if(selected)show(selected)}}
load();watchTask();
</script></body></html>"""
