"""Static, server-less dashboard generator (redesigned UI).

Builds ONE self-contained `dashboard.html` with all job data, CSS and JS inlined, plus
tailored resume/cover HTML embedded for offline preview. Opens by double-click, no server.

Two entry points share one renderer:
  * build_static(db)            -> from the live SQLite DB (the daily GitHub-Actions run)
  * build_from_records(records) -> from plain job dicts (the agent's enriched/scored set,
                                   incl. LLM scores + tailored docs, built in a Claude/
                                   OpenClaw session where the reasoning happens)

A record is a dict with: id, company, title, location, url, score, state, score_json,
posted_at, age_days, jd, resume_html, cover_html.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import output_dir
from .db import DB


def _records_from_db(db: DB) -> list[dict]:
    out = []
    for j in db.all():
        if j["state"] == "rejected":
            continue
        d = output_dir() / j["id"]
        def _read(name):
            p = d / name
            return p.read_text(encoding="utf-8") if p.exists() else ""
        from .util import age_days
        out.append({
            "id": j["id"], "company": j["company"], "title": j["title"],
            "location": j.get("location", ""), "url": j.get("url", ""),
            "score": j.get("score"), "state": j["state"],
            "score_json": j.get("score_json") or {},
            "posted_at": j.get("posted_at", ""), "age_days": age_days(j.get("posted_at", "")),
            "jd": (j.get("jd_text") or "")[:8000],
            "resume_html": _read("resume.html"),
            "cover_html": _read("cover_letter.html"),
        })
    return out


def build_from_records(records: list[dict]) -> str:
    jobs = sorted(records, key=lambda x: (x.get("score") or 0), reverse=True)
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j["state"]] = counts.get(j["state"], 0) + 1
    strong = sum(1 for j in jobs if (j.get("score") or 0) >= 75)
    fresh = sum(1 for j in jobs if (j.get("age_days") is not None and j["age_days"] <= 1))
    live = sum(1 for j in jobs if (j.get("score_json") or {}).get("link_state") == "live")
    tailored = sum(1 for j in jobs if j.get("resume_html") or j.get("cover_html"))
    stats = {"total": len(jobs), "strong": strong, "fresh": fresh, "live": live, "tailored": tailored}
    # Escape "</" so embedded JD/resume HTML can never prematurely close the <script> block.
    data = json.dumps(jobs, ensure_ascii=False).replace("</", "<\\/")
    return (_TEMPLATE
            .replace("__DATA__", data)
            .replace("__STATS__", json.dumps(stats, ensure_ascii=False))
            .replace("__COUNTS__", json.dumps(counts, ensure_ascii=False)))


def build_static(db: DB) -> str:
    return build_from_records(_records_from_db(db))


def write_static(db: DB, path: Path | None = None) -> Path:
    p = path or (output_dir() / "dashboard.html")
    p.write_text(build_static(db), encoding="utf-8")
    return p


_TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fuel-Cell Job Radar — Vallabh Pataneni</title>
<style>
:root{
  --bg:#0b1220; --panel:#11192b; --panel2:#0e1626; --card:#131d31; --line:#1f2c45;
  --ink:#e8eef7; --muted:#93a1b8; --faint:#64748b;
  --accent:#19c37d; --accent2:#1f9d72; --blue:#4d8dff; --violet:#a78bfa; --amber:#f5b34a; --red:#fb7185;
  --shadow:0 8px 30px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{font-family:-apple-system,'Segoe UI',Roboto,Inter,Arial,sans-serif;background:
  radial-gradient(1200px 600px at 80% -10%,rgba(25,195,125,.10),transparent 60%),
  radial-gradient(900px 500px at -10% 0%,rgba(77,141,255,.10),transparent 55%),var(--bg);
  color:var(--ink);min-height:100vh}
.wrap{max-width:1120px;margin:0 auto;padding:0 18px 80px}
/* hero */
.hero{padding:30px 0 8px}
.hero h1{margin:0;font-size:26px;letter-spacing:.2px}
.hero h1 .spark{color:var(--accent)}
.hero .sub{color:var(--muted);font-size:13.5px;margin-top:6px;max-width:720px;line-height:1.5}
.stats{display:flex;gap:12px;flex-wrap:wrap;margin:18px 0 6px}
.stat{background:linear-gradient(180deg,var(--panel),var(--panel2));border:1px solid var(--line);
  border-radius:14px;padding:12px 16px;min-width:120px;box-shadow:var(--shadow)}
.stat .n{font-size:24px;font-weight:800;line-height:1}
.stat .l{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--faint);margin-top:6px}
.stat.green .n{color:var(--accent)} .stat.blue .n{color:var(--blue)} .stat.violet .n{color:var(--violet)}
/* controls */
.controls{position:sticky;top:0;z-index:5;background:rgba(11,18,32,.85);backdrop-filter:blur(8px);
  border:1px solid var(--line);border-radius:14px;padding:10px 12px;display:flex;gap:10px;
  flex-wrap:wrap;align-items:center;margin:16px 0 18px;box-shadow:var(--shadow)}
.controls input[type=text],.controls select{background:var(--panel2);border:1px solid var(--line);
  color:var(--ink);padding:8px 11px;border-radius:9px;font-size:14px;outline:none}
.controls input[type=text]:focus,.controls select:focus{border-color:var(--accent)}
.controls label{font-size:12.5px;color:var(--muted);display:flex;align-items:center;gap:6px}
.seg{display:flex;background:var(--panel2);border:1px solid var(--line);border-radius:9px;overflow:hidden}
.seg button{background:transparent;color:var(--muted);border:0;padding:7px 12px;font-size:12.5px;cursor:pointer}
.seg button.active{background:var(--accent);color:#06210f;font-weight:700}
input[type=range]{accent-color:var(--accent)}
/* job card */
.job{position:relative;background:linear-gradient(180deg,var(--card),var(--panel2));
  border:1px solid var(--line);border-radius:16px;padding:16px 18px 14px;margin:0 0 14px;
  display:flex;gap:16px;box-shadow:var(--shadow);transition:transform .12s,border-color .12s}
.job:hover{transform:translateY(-2px);border-color:#2b3c5e}
.job.tailored{border-color:rgba(25,195,125,.55);box-shadow:0 8px 30px rgba(25,195,125,.10)}
.ribbon{position:absolute;top:14px;right:-1px;background:var(--accent);color:#06210f;font-size:11px;
  font-weight:800;padding:4px 12px;border-radius:8px 0 0 8px;letter-spacing:.3px}
/* score ring */
.ring{--p:0;--c:var(--faint);flex:0 0 auto;width:60px;height:60px;border-radius:50%;
  background:conic-gradient(var(--c) calc(var(--p)*1%),#22324d 0);display:flex;align-items:center;justify-content:center}
.ring i{width:48px;height:48px;border-radius:50%;background:var(--panel2);display:flex;flex-direction:column;
  align-items:center;justify-content:center;font-style:normal}
.ring b{font-size:18px;line-height:1} .ring s{font-size:8px;color:var(--faint);text-decoration:none;letter-spacing:.5px}
.main{flex:1;min-width:0}
.main h3{margin:0 0 3px;font-size:16.5px;line-height:1.25}
.co{color:var(--muted);font-size:13px}
.co .dot{opacity:.5;margin:0 6px}
.tags{margin:9px 0 8px;display:flex;gap:6px;flex-wrap:wrap}
.tag{font-size:11.5px;border-radius:999px;padding:2px 10px;border:1px solid transparent;white-space:nowrap}
.t-sector{background:rgba(25,195,125,.12);color:var(--accent);border-color:rgba(25,195,125,.3)}
.t-phd{background:rgba(167,139,250,.13);color:var(--violet);border-color:rgba(167,139,250,.3)}
.t-de{background:rgba(245,179,74,.12);color:var(--amber);border-color:rgba(245,179,74,.3)}
.t-tier{background:rgba(77,141,255,.12);color:var(--blue);border-color:rgba(77,141,255,.3)}
.t-fresh{background:rgba(25,195,125,.12);color:var(--accent)}
.t-live{background:rgba(25,195,125,.10);color:var(--accent)}
.t-unv{background:rgba(245,179,74,.10);color:var(--amber)}
.t-gone{background:rgba(251,113,133,.12);color:var(--red)}
.t-muted{background:rgba(148,163,184,.10);color:var(--faint)}
.why{margin:4px 0 10px;padding-left:0;list-style:none}
.why li{font-size:13px;color:#c7d3e6;margin:3px 0;padding-left:18px;position:relative}
.why li:before{content:'';position:absolute;left:2px;top:7px;width:6px;height:6px;border-radius:50%;background:var(--accent2)}
.acts{display:flex;gap:8px;flex-wrap:wrap}
button.btn{cursor:pointer;border:1px solid var(--line);border-radius:9px;padding:7px 12px;font-size:12.5px;
  font-weight:600;background:var(--panel2);color:var(--ink)}
button.btn:hover{border-color:#33456a}
.btn.primary{background:var(--blue);border-color:var(--blue);color:#04122e}
.btn.go{background:var(--accent);border-color:var(--accent);color:#06210f}
.btn.ok{background:transparent;color:var(--accent);border-color:rgba(25,195,125,.4)}
.btn.no{background:transparent;color:var(--red);border-color:rgba(251,113,133,.4)}
a.plain{color:inherit;text-decoration:none}
.empty{color:var(--faint);text-align:center;padding:40px}
/* modal */
dialog{border:0;border-radius:16px;max-width:980px;width:94%;padding:0;background:var(--panel);
  color:var(--ink);box-shadow:0 30px 80px rgba(0,0,0,.6)}
dialog::backdrop{background:rgba(3,7,15,.66);backdrop-filter:blur(3px)}
.dhead{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;padding:18px 20px 8px}
.dhead h2{margin:0;font-size:18px}.dhead .co{margin-top:3px}
.dtabs{display:flex;gap:8px;padding:6px 20px 0;flex-wrap:wrap;border-bottom:1px solid var(--line)}
.dtab{background:transparent;border:0;border-bottom:2px solid transparent;color:var(--muted);
  padding:8px 4px;font-size:13.5px;font-weight:600;cursor:pointer}
.dtab.active{color:var(--ink);border-color:var(--accent)}
.dbody{padding:16px 20px 22px}
pre.jd{white-space:pre-wrap;font-family:inherit;font-size:13.5px;line-height:1.55;color:#cdd8ea;
  background:var(--panel2);border:1px solid var(--line);border-radius:10px;padding:14px;max-height:60vh;overflow:auto}
iframe{width:100%;height:70vh;border:1px solid var(--line);border-radius:10px;background:#fff}
/* command bar */
#cmdbar{position:fixed;left:50%;transform:translateX(-50%);bottom:18px;background:#0a1424;
  border:1px solid var(--line);color:var(--ink);padding:10px 14px;border-radius:14px;display:none;
  align-items:center;gap:10px;font-size:12.5px;box-shadow:var(--shadow);max-width:94%;flex-wrap:wrap;z-index:9}
#cmdbar code{background:#0f1d34;padding:5px 9px;border-radius:7px;color:#cfe0ff;font-size:12px}
.foot{color:var(--faint);font-size:12px;text-align:center;margin-top:24px;line-height:1.6}
</style></head><body>
<div class="wrap">
 <div class="hero">
  <h1><span class="spark">⚡</span> Fuel-Cell Job Radar</h1>
  <div class="sub">Fresh hydrogen &amp; fuel-cell roles across Germany and Europe, scored against
   Vallabh's profile (fuel-cell systems, operating strategy &amp; simulation). Strongest matches first.
   Tailored résumé and cover letter are embedded for the top picks. Click <b>Open posting</b> to verify any link.</div>
  <div class="stats" id="stats"></div>
 </div>

 <div class="controls">
  <input type="text" id="q" placeholder="search company or title" style="flex:1;min-width:160px">
  <label>min fit <input type="range" id="minScore" min="0" max="100" value="0" step="5" style="width:120px">
   <b id="minLbl" style="color:var(--ink);width:26px;display:inline-block">0</b></label>
  <select id="sector"><option value="">all sectors</option><option>aviation</option><option>rail</option>
   <option>heavy</option><option>stationary</option><option>research</option><option>other</option></select>
  <div class="seg" id="quick">
   <button data-f="all" class="active">All</button>
   <button data-f="strong">Strong</button>
   <button data-f="tailored">Tailored</button>
   <button data-f="thesis">Thesis/Werkstudent</button>
  </div>
 </div>

 <div id="list"></div>
 <div class="foot">Server-less dashboard · regenerate with <code>python -m jobauto dashboard</code> ·
  approvals build CLI commands you run where the database lives.</div>
</div>

<dialog id="modal"><div>
 <div class="dhead">
  <div><h2 id="m_title"></h2><div class="co" id="m_co"></div></div>
  <button class="btn" onclick="document.getElementById('modal').close()">Close ✕</button>
 </div>
 <div class="dtabs" id="m_tabs"></div>
 <div class="dbody" id="m_body"></div>
</div></dialog>

<div id="cmdbar"><span style="color:var(--muted)">Selection:</span>
 <code id="cmd_a">approve —</code><code id="cmd_r">reject —</code>
 <button class="btn primary" onclick="copyCmds()">Copy</button>
 <button class="btn" onclick="clearSel()">Clear</button></div>

<script>
const JOBS=__DATA__, STATS=__STATS__, COUNTS=__COUNTS__;
const sel={approve:new Set(),reject:new Set()};
let quick='all';
const esc=s=>(s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const ringColor=s=>s>=85?'var(--accent)':s>=70?'var(--blue)':s>=50?'var(--amber)':'var(--faint)';

function renderStats(){
 const s=STATS;
 document.getElementById('stats').innerHTML=
  `<div class="stat"><div class="n">${s.total}</div><div class="l">live postings</div></div>
   <div class="stat green"><div class="n">${s.strong}</div><div class="l">strong fit ≥75</div></div>
   <div class="stat blue"><div class="n">${s.fresh}</div><div class="l">fresh ≤1 day</div></div>
   <div class="stat green"><div class="n">${s.live}</div><div class="l">links verified</div></div>
   <div class="stat violet"><div class="n">${s.tailored}</div><div class="l">tailored ready</div></div>`;
}
function freshTag(j){
 if(j.age_days==null)return '<span class="tag t-muted">date n/a</span>';
 const t=j.age_days<=0?'today':j.age_days+'d ago';
 return `<span class="tag t-fresh">🕑 ${t}</span>`;
}
function linkTag(sj){
 if(sj.link_state==='live')return '<span class="tag t-live">✓ link verified</span>';
 if(sj.link_state==='gone')return '<span class="tag t-gone">⚠ link dead</span>';
 if(sj.link_state==='unverified')return '<span class="tag t-unv">link unverified</span>';
 return '';
}
function matchesQuick(j){
 const sj=j.score_json||{};
 if(quick==='strong')return (j.score||0)>=75;
 if(quick==='tailored')return !!(j.resume_html||j.cover_html);
 if(quick==='thesis')return /thesis|werkstudent|masterarbeit|abschlussarbeit|praktik|semesterarbeit|student/i.test((j.title||'')+' '+(sj.work_type||''));
 return true;
}
function filtered(){
 const q=document.getElementById('q').value.toLowerCase();
 const ms=+document.getElementById('minScore').value||0;
 const sec=document.getElementById('sector').value;
 return JOBS.filter(j=>{
  const sj=j.score_json||{};
  if(!matchesQuick(j))return false;
  if(q&&!((j.company+' '+j.title).toLowerCase().includes(q)))return false;
  if((j.score||0)<ms)return false;
  if(sec&&sj.sector!==sec)return false;
  return true;
 });
}
function card(j){
 const sj=j.score_json||{};
 const tailored=!!(j.resume_html||j.cover_html);
 let tags='';
 if(sj.sector)tags+=`<span class="tag t-sector">${esc(sj.sector)}</span>`;
 if(sj.is_phd)tags+='<span class="tag t-phd">PhD/research</span>';
 if(sj.work_type)tags+=`<span class="tag t-tier">${esc(sj.work_type)}</span>`;
 if(sj.german_required)tags+=`<span class="tag t-de">German ${esc(sj.german_required)}</span>`;
 tags+=freshTag(j); tags+=linkTag(sj);
 const why=(sj.reasons||[]).slice(0,3).map(r=>`<li>${esc(r)}</li>`).join('');
 const docBtns=(j.resume_html?`<button class="btn primary" onclick="openJob('${j.id}','resume')">Résumé</button>`:'')
   +(j.cover_html?`<button class="btn primary" onclick="openJob('${j.id}','cover')">Cover letter</button>`:'');
 const p=Math.max(0,Math.min(100,j.score||0));
 return `<div class="job${tailored?' tailored':''}">
  ${tailored?'<div class="ribbon">TAILORED ✦</div>':''}
  <div class="ring" style="--p:${p};--c:${ringColor(j.score||0)}"><i><b>${j.score??'—'}</b><s>FIT</s></i></div>
  <div class="main">
   <h3>${esc(j.title)}</h3>
   <div class="co">${esc(j.company)}<span class="dot">·</span>${esc(j.location||'location n/a')}</div>
   <div class="tags">${tags}</div>
   <ul class="why">${why}</ul>
   <div class="acts">
    <a class="plain" href="${esc(j.url||'#')}" target="_blank"><button class="btn go">Open posting ↗</button></a>
    <button class="btn" onclick="openJob('${j.id}','jd')">View JD</button>
    ${docBtns}
    <button class="btn ok" onclick="pick('approve','${j.id}')">✓ Approve</button>
    <button class="btn no" onclick="pick('reject','${j.id}')">✕ Reject</button>
   </div>
  </div></div>`;
}
function render(){
 const f=filtered();
 document.getElementById('list').innerHTML=f.map(card).join('')||'<div class="empty">No matches with these filters.</div>';
}
function openJob(id,which){
 const j=JOBS.find(x=>x.id===id);
 document.getElementById('m_title').textContent=j.title;
 document.getElementById('m_co').textContent=j.company+'  ·  '+(j.location||'');
 let tabs=[['jd','Job description']];
 if(j.resume_html)tabs.push(['resume','Résumé ✦']);
 if(j.cover_html)tabs.push(['cover','Cover letter ✦']);
 tabs.push(['open','Open posting ↗']);
 document.getElementById('m_tabs').innerHTML=tabs.map(([k,l])=>
   `<button class="dtab" data-k="${k}" onclick="showDoc('${id}','${k}')">${l}</button>`).join('');
 showDoc(id,which||'jd');
 document.getElementById('modal').showModal();
}
function showDoc(id,which){
 const j=JOBS.find(x=>x.id===id);
 document.querySelectorAll('#m_tabs .dtab').forEach(b=>b.classList.toggle('active',b.dataset.k===which));
 const body=document.getElementById('m_body');
 if(which==='open'){window.open(j.url||'#','_blank');return;}
 if(which==='jd'){body.innerHTML=`<pre class="jd">${esc(j.jd)||'(no description captured)'}</pre>`;return;}
 const html=which==='resume'?j.resume_html:j.cover_html;
 const slug=(j.score_json||{}).packet;
 const note=slug?`<div style="background:#0f1d34;border:1px solid #1f2c45;border-radius:8px;padding:8px 11px;margin:0 0 8px;font-size:12.5px;color:#bcd">✏️ Editable source: <code>Job automation/applications/${slug}/</code> — open <code>${which}${which==='cover'?'_letter':''}.html</code> to edit inline, or edit the <code>.md</code> and run <code>python -m jobauto render ${slug}</code></div>`:'';
 body.innerHTML=note;
 const ifr=document.createElement('iframe');ifr.srcdoc=html;body.appendChild(ifr);
}
function pick(kind,id){sel[kind].add(id);sel[kind==='approve'?'reject':'approve'].delete(id);updateBar();}
function updateBar(){
 const a=[...sel.approve],r=[...sel.reject];
 document.getElementById('cmd_a').textContent='approve '+(a.join(' ')||'—');
 document.getElementById('cmd_r').textContent='reject '+(r.join(' ')||'—');
 document.getElementById('cmdbar').style.display=(a.length||r.length)?'flex':'none';
}
function copyCmds(){
 const a=[...sel.approve],r=[...sel.reject],lines=[];
 if(a.length)lines.push('python -m jobauto approve '+a.join(' '));
 if(r.length)lines.push('python -m jobauto reject '+r.join(' '));
 navigator.clipboard.writeText(lines.join('\n')).then(()=>alert('Copied:\n'+lines.join('\n')));
}
function clearSel(){sel.approve.clear();sel.reject.clear();updateBar();}
document.getElementById('minScore').addEventListener('input',e=>{document.getElementById('minLbl').textContent=e.target.value;render();});
['q','sector'].forEach(id=>document.getElementById(id).addEventListener('input',render));
document.querySelectorAll('#quick button').forEach(b=>b.addEventListener('click',()=>{
 quick=b.dataset.f;document.querySelectorAll('#quick button').forEach(x=>x.classList.remove('active'));
 b.classList.add('active');render();
}));
renderStats();render();
</script></body></html>"""
