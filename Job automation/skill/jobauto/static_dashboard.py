"""Static, server-less dashboard generator.

Why: the FastAPI dashboard needs a running localhost process + writable DB, which does
not work in an ephemeral cloud/GitHub web session. This builds ONE self-contained
`dashboard.html` (job data, CSS and JS all inlined, plus the tailored docs embedded for
offline preview). It opens by double-click anywhere, no server.

Approve/reject in a static file cannot write the DB, so the page builds the exact CLI
commands for your selection with a copy button (run them wherever the DB lives).
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import output_dir
from .db import DB


def _job_payload(db: DB) -> list[dict]:
    out = []
    for j in db.all():
        # include unscored DISCOVERED jobs too, so a discovery-only run (no LLM, e.g.
        # GitHub Actions) still shows fresh, link-validated postings. Scoring enriches later.
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
    out.sort(key=lambda x: x.get("score") or 0, reverse=True)
    return out


def build_static(db: DB) -> str:
    jobs = _job_payload(db)
    counts: dict[str, int] = {}
    for j in jobs:
        counts[j["state"]] = counts.get(j["state"], 0) + 1
    data = json.dumps(jobs, ensure_ascii=False)
    counts_json = json.dumps(counts, ensure_ascii=False)
    # NOTE: braces in the template are escaped ({{ }}) so .format leaves the JS/CSS intact.
    return _TEMPLATE.replace("__DATA__", data).replace("__COUNTS__", counts_json)


def write_static(db: DB, path: Path | None = None) -> Path:
    p = path or (output_dir() / "dashboard.html")
    p.write_text(build_static(db), encoding="utf-8")
    return p


_TEMPLATE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Automation — Static Dashboard</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:-apple-system,'Segoe UI',Roboto,Arial,sans-serif;background:#f4f6f8;color:#0f172a}
.wrap{max-width:1040px;margin:0 auto;padding:0 16px 60px}
header.top{background:linear-gradient(120deg,#0b6e4f,#0e8a63);color:#fff;padding:20px 0 16px;box-shadow:0 2px 10px rgba(0,0,0,.08)}
header.top h1{margin:0;font-size:21px}header.top .sub{opacity:.9;font-size:13px;margin-top:3px}
.cards{display:flex;gap:10px;flex-wrap:wrap;margin:16px 0 4px}
.card{background:#fff;border:1px solid #e6eaef;border-radius:12px;padding:10px 14px;min-width:96px}
.card .n{font-size:22px;font-weight:700}.card .l{font-size:11px;text-transform:uppercase;letter-spacing:.7px;color:#64748b}
.controls{background:#fff;border:1px solid #e6eaef;border-radius:12px;padding:12px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:14px 0}
.controls input,.controls select{padding:7px 9px;border:1px solid #d6dde6;border-radius:8px;font-size:14px}
.job{background:#fff;border:1px solid #e6eaef;border-radius:14px;padding:14px 16px;margin:0 0 12px;display:flex;gap:14px}
.badge{min-width:52px;height:52px;border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:700;flex:0 0 auto}
.jobmain{flex:1}.jobmain h3{margin:0 0 2px;font-size:16px}.co{color:#475569;font-size:13.5px}
.tags{margin:7px 0 5px;display:flex;gap:6px;flex-wrap:wrap}
.tag{background:#eef2f6;border-radius:6px;padding:1px 8px;font-size:12px;color:#475569}
.tag.phd{background:#f3e8ff;color:#7c3aed}.tag.de{background:#fff7ed;color:#b45309}.tag.sector{background:#ecfdf5;color:#0b6e4f}
.pill{border-radius:6px;padding:1px 8px;color:#fff;font-size:11px;font-weight:600}
ul.reasons{margin:5px 0 9px;padding-left:18px;color:#334155;font-size:13.5px}
button{cursor:pointer;border:0;border-radius:8px;padding:6px 12px;font-size:13px;color:#fff;font-weight:600}
.ok{background:#0b6e4f}.no{background:#b42318}.ghost{background:#fff;color:#334155;border:1px solid #d6dde6}.blue{background:#2563eb}
a{color:#2563eb;text-decoration:none}
dialog{border:0;border-radius:14px;max-width:900px;width:92%;padding:0}
dialog .dwrap{padding:18px}
pre.jd{white-space:pre-wrap;font-family:inherit;font-size:13.5px;background:#f6f8fa;border-radius:8px;padding:10px;max-height:300px;overflow:auto}
iframe{width:100%;height:560px;border:1px solid #e6eaef;border-radius:10px;background:#fff}
.tabbtn{background:#eef2f6;color:#334155;margin-right:6px}.tabbtn.active{background:#2563eb;color:#fff}
#cmdbar{position:fixed;bottom:0;left:0;right:0;background:#0f172a;color:#fff;padding:10px 16px;display:none;align-items:center;gap:12px;font-size:13px}
#cmdbar code{background:#1e293b;padding:4px 8px;border-radius:6px}
</style></head><body>
<header class="top"><div class="wrap"><h1>⚡ Fuel-Cell Job Automation — Static Dashboard</h1>
<div class="sub">Server-less. Generated by <code>python -m jobauto dashboard</code>. Approvals build CLI commands you run where the DB lives.</div></div></header>
<div class="wrap">
 <div class="cards" id="cards"></div>
 <div class="controls">
  <input id="q" placeholder="search company / title" style="flex:1;min-width:160px">
  <label style="font-size:13px;color:#475569">min score <input id="minScore" type="number" value="0" min="0" max="100" style="width:64px"></label>
  <select id="sector"><option value="">all sectors</option><option>aviation</option><option>rail</option><option>heavy</option><option>other</option></select>
  <label style="font-size:13px;color:#475569"><input type="checkbox" id="phd"> PhD only</label>
 </div>
 <h2 id="qhead">Review queue</h2>
 <div id="list"></div>
</div>

<dialog id="modal"><div class="dwrap">
  <button class="ghost" style="float:right" onclick="document.getElementById('modal').close()">Close</button>
  <h2 id="m_title" style="margin:0 0 4px"></h2><div class="co" id="m_co"></div>
  <div style="margin:10px 0"><a id="m_url" target="_blank"><button class="ghost">Open posting ↗</button></a></div>
  <div id="m_tabs" style="margin:8px 0"></div>
  <div id="m_body"></div>
</div></dialog>

<div id="cmdbar"><span>Selected:</span><code id="cmd_approve">approve —</code><code id="cmd_reject">reject —</code>
 <button class="blue" onclick="copyCmds()">Copy commands</button>
 <button class="ghost" onclick="clearSel()">Clear</button></div>

<script>
const JOBS = __DATA__; const COUNTS = __COUNTS__;
const sel = {approve:new Set(), reject:new Set()};
const scoreColor = s => s>=85?'#0b6e4f':s>=70?'#2563eb':s>=50?'#b45309':'#94a3b8';
const esc = s => (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

function renderCards(){
  const order=['discovered','scored','approved','docs_ready','prefilled','applied'];
  let total=Object.values(COUNTS).reduce((a,b)=>a+b,0);
  let h=`<div class="card"><div class="n">${total}</div><div class="l">total</div></div>`;
  order.forEach(k=>{if(COUNTS[k])h+=`<div class="card"><div class="n">${COUNTS[k]}</div><div class="l">${k.replace('_',' ')}</div></div>`});
  document.getElementById('cards').innerHTML=h;
}
function filtered(){
  const q=document.getElementById('q').value.toLowerCase();
  const ms=+document.getElementById('minScore').value||0;
  const sec=document.getElementById('sector').value;
  const phd=document.getElementById('phd').checked;
  return JOBS.filter(j=>{
    const sj=j.score_json||{};
    if(q && !((j.company+' '+j.title).toLowerCase().includes(q))) return false;
    if((j.score||0)<ms) return false;
    if(sec && sj.sector!==sec) return false;
    if(phd && !sj.is_phd) return false;
    return true;
  });
}
function card(j){
  const sj=j.score_json||{};
  let tags='';
  if(sj.sector)tags+=`<span class="tag sector">${esc(sj.sector)}</span>`;
  if(sj.is_phd)tags+='<span class="tag phd">PhD</span>';
  if(sj.german_required)tags+=`<span class="tag de">German ${esc(sj.german_required)}</span>`;
  if(sj.tier)tags+=`<span class="tag">tier ${esc(sj.tier)}</span>`;
  if(j.age_days!=null)tags+=`<span class="tag" style="background:#dcfce7;color:#166534">${j.age_days<=0?'today':j.age_days+'d ago'}</span>`;
  else tags+='<span class="tag" style="background:#fef9c3;color:#854d0e">date?</span>';
  if(sj.link_ok===false)tags+='<span class="tag" style="background:#fee2e2;color:#991b1b">⚠ link dead</span>';
  const reasons=(sj.reasons||[]).slice(0,4).map(r=>`<li>${esc(r)}</li>`).join('');
  const docs=(j.resume_html||j.cover_html)?`<button class="blue" onclick="openJob('${j.id}')">View docs &amp; JD</button>`:`<button class="ghost" onclick="openJob('${j.id}')">View JD</button>`;
  return `<div class="job"><div class="badge" style="background:${scoreColor(j.score)}">${j.score??'—'}</div>
   <div class="jobmain"><h3>${esc(j.title)}</h3>
   <div class="co">${esc(j.company)} · ${esc(j.location||'n/a')} <span class="pill" style="background:#64748b">${j.state}</span></div>
   <div class="tags">${tags}</div><ul class="reasons">${reasons}</ul>
   <div style="display:flex;gap:8px;flex-wrap:wrap">
     <a href="${esc(j.url||'#')}" target="_blank"><button class="ghost">Open posting ↗</button></a>
     ${docs}
     <button class="ok" onclick="pick('approve','${j.id}')">✓ Approve</button>
     <button class="no" onclick="pick('reject','${j.id}')">✕ Reject</button>
   </div></div></div>`;
}
function render(){
  const f=filtered();
  document.getElementById('qhead').textContent=`Review queue · ${f.length} shown`;
  document.getElementById('list').innerHTML=f.map(card).join('')||'<p style="color:#64748b">No matches.</p>';
}
let curDoc='jd';
function openJob(id){
  const j=JOBS.find(x=>x.id===id); curDoc='jd';
  document.getElementById('m_title').textContent=j.title;
  document.getElementById('m_co').textContent=j.company+' · '+(j.location||'');
  document.getElementById('m_url').href=j.url||'#';
  let tabs=`<button class="tabbtn active" onclick="showDoc('${id}','jd',this)">Job description</button>`;
  if(j.resume_html)tabs+=`<button class="tabbtn" onclick="showDoc('${id}','resume',this)">Résumé</button>`;
  if(j.cover_html)tabs+=`<button class="tabbtn" onclick="showDoc('${id}','cover',this)">Cover letter</button>`;
  document.getElementById('m_tabs').innerHTML=tabs;
  showDoc(id,'jd',document.querySelector('#m_tabs .tabbtn'));
  document.getElementById('modal').showModal();
}
function showDoc(id,which,btn){
  document.querySelectorAll('#m_tabs .tabbtn').forEach(b=>b.classList.remove('active'));
  if(btn)btn.classList.add('active');
  const j=JOBS.find(x=>x.id===id);
  const body=document.getElementById('m_body');
  if(which==='jd'){body.innerHTML=`<pre class="jd">${esc(j.jd)||'(no JD captured)'}</pre>`;}
  else{const html=which==='resume'?j.resume_html:j.cover_html;
    const ifr=document.createElement('iframe');ifr.srcdoc=html;body.innerHTML='';body.appendChild(ifr);}
}
function pick(kind,id){
  sel[kind].add(id); sel[kind==='approve'?'reject':'approve'].delete(id); updateBar();
}
function updateBar(){
  const a=[...sel.approve], r=[...sel.reject];
  document.getElementById('cmd_approve').textContent='python -m jobauto approve '+(a.join(' ')||'—');
  document.getElementById('cmd_reject').textContent='python -m jobauto reject '+(r.join(' ')||'—');
  document.getElementById('cmdbar').style.display=(a.length||r.length)?'flex':'none';
}
function copyCmds(){
  const a=[...sel.approve], r=[...sel.reject]; let lines=[];
  if(a.length)lines.push('python -m jobauto approve '+a.join(' '));
  if(r.length)lines.push('python -m jobauto reject '+r.join(' '));
  navigator.clipboard.writeText(lines.join('\n')).then(()=>alert('Copied:\n'+lines.join('\n')));
}
function clearSel(){sel.approve.clear();sel.reject.clear();updateBar();}
['q','minScore','sector','phd'].forEach(id=>document.getElementById(id).addEventListener('input',render));
renderCards(); render();
</script></body></html>"""
