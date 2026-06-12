"""Render an application's editable Markdown source into a styled, ATS-friendly HTML
document, with an optional in-browser editor toolbar (Edit, autosave, Download, Print).

The Markdown file is the SOURCE OF TRUTH the candidate owns and edits in plain language.
`python -m jobauto render <slug>` rebuilds the HTML (and PDF, if weasyprint is installed)
from it, so edits always flow Markdown -> HTML -> PDF.

Markdown subset supported (kept simple on purpose, no heavy deps required):
  # H1            -> name / title
  ## H2           -> section heading (Summary, Experience, ...)
  ### H3          -> entry heading (role, education line)
  **bold**  *italic*
  - bullet
  ---             -> horizontal rule
  plain line      -> paragraph
"""
from __future__ import annotations

import html as _html
import re
from pathlib import Path

RESUME_CSS = """
:root{--accent:#0b6e4f;--ink:#1a1a1a;--muted:#566;--line:#e3e6ea}
*{box-sizing:border-box}body{font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
 color:var(--ink);max-width:840px;margin:24px auto;padding:0 40px;line-height:1.5;font-size:14.5px}
h1{font-size:27px;margin:0 0 2px;letter-spacing:.2px}
h1+p{color:var(--accent);font-weight:600;margin:0 0 4px}
h2{font-size:12px;text-transform:uppercase;letter-spacing:1.4px;color:var(--accent);
 border-bottom:2px solid var(--line);padding-bottom:3px;margin:16px 0 7px}
h3{font-size:14.5px;margin:9px 0 1px}
p{margin:5px 0}ul{margin:5px 0 8px;padding-left:18px}li{margin:3px 0}
hr{border:0;border-top:1px solid var(--line);margin:10px 0}
em{color:var(--muted);font-style:normal;font-size:12.8px}
a{color:var(--accent);text-decoration:none}
@media print{body{margin:0;max-width:none;font-size:11.6px;padding:0 12px}.toolbar{display:none!important}}
"""

_EDITOR_JS = """
<div class="toolbar" style="position:sticky;top:0;z-index:9;display:flex;gap:8px;align-items:center;
 background:#0b1220;color:#fff;padding:8px 12px;margin:-24px -40px 16px;font:13px -apple-system,Segoe UI,Arial">
 <strong style="margin-right:auto">Editable document</strong>
 <button onclick="toggleEdit(this)" style="cursor:pointer;border:0;border-radius:7px;padding:6px 12px;background:#19c37d;color:#06210f;font-weight:700">✏️ Edit</button>
 <button onclick="dl()" style="cursor:pointer;border:0;border-radius:7px;padding:6px 12px;background:#2b3c5e;color:#fff">⬇ Download</button>
 <button onclick="window.print()" style="cursor:pointer;border:0;border-radius:7px;padding:6px 12px;background:#2b3c5e;color:#fff">🖨 PDF</button>
 <span id="saved" style="opacity:.7;font-size:12px"></span>
</div>
<div id="doc">__BODY__</div>
<script>
const KEY='app:'+location.pathname.split('/').pop();
const doc=document.getElementById('doc');
try{const s=localStorage.getItem(KEY);if(s){doc.innerHTML=s;mark('restored your edits')}}catch(e){}
function toggleEdit(b){const on=doc.isContentEditable;doc.contentEditable=!on;
 doc.style.outline=on?'none':'2px dashed #19c37d';doc.style.padding=on?'0':'6px';
 b.textContent=on?'✏️ Edit':'✓ Done';if(on)save();}
doc.addEventListener('input',()=>{clearTimeout(window._t);window._t=setTimeout(save,500)});
function save(){try{localStorage.setItem(KEY,doc.innerHTML);mark('saved locally '+new Date().toLocaleTimeString())}catch(e){}}
function mark(m){document.getElementById('saved').textContent=m}
function dl(){const html='<!doctype html><meta charset=utf-8><style>'+document.querySelector('style').textContent+'</style>'+doc.outerHTML;
 const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([html],{type:'text/html'}));
 a.download=(location.pathname.split('/').pop()||'document.html');a.click();}
</script>
"""


def md_to_html(md: str) -> str:
    """Markdown subset -> HTML body. Uses python-markdown if present, else a small parser."""
    try:
        import markdown  # optional, nicer tables/etc.
        return markdown.markdown(md, extensions=["sane_lists"])
    except Exception:
        pass
    out, lines, i = [], md.splitlines(), 0
    def inline(s: str) -> str:
        s = _html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
        s = re.sub(r"\[(.+?)\]\((.+?)\)", r'<a href="\2">\1</a>', s)
        return s
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1; continue
        if ln.strip() == "---":
            out.append("<hr>"); i += 1; continue
        if ln.startswith("### "):
            out.append(f"<h3>{inline(ln[4:])}</h3>"); i += 1; continue
        if ln.startswith("## "):
            out.append(f"<h2>{inline(ln[3:])}</h2>"); i += 1; continue
        if ln.startswith("# "):
            out.append(f"<h1>{inline(ln[2:])}</h1>"); i += 1; continue
        if ln.lstrip().startswith("- "):
            out.append("<ul>")
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                out.append(f"<li>{inline(lines[i].lstrip()[2:])}</li>"); i += 1
            out.append("</ul>"); continue
        out.append(f"<p>{inline(ln)}</p>"); i += 1
    return "\n".join(out)


def render_html(md: str, title: str, editable: bool = True) -> str:
    body = md_to_html(md)
    inner = _EDITOR_JS.replace("__BODY__", body) if editable else body
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{_html.escape(title)}</title><style>{RESUME_CSS}</style></head>'
            f'<body>{inner}</body></html>')


def render_dir(slug_dir: Path) -> list[Path]:
    """Render every *.md in a packet dir to a sibling editable .html (+ PDF if possible)."""
    written = []
    for md_path in sorted(slug_dir.glob("*.md")):
        if md_path.name.upper() == "README.MD":
            continue
        md = md_path.read_text(encoding="utf-8")
        title = next((l[2:] for l in md.splitlines() if l.startswith("# ")), md_path.stem)
        html = render_html(md, title, editable=True)
        hp = md_path.with_suffix(".html")
        hp.write_text(html, encoding="utf-8")
        written.append(hp)
        try:
            from weasyprint import HTML  # optional
            HTML(string=render_html(md, title, editable=False)).write_pdf(str(md_path.with_suffix(".pdf")))
            written.append(md_path.with_suffix(".pdf"))
        except Exception:
            pass
    return written
