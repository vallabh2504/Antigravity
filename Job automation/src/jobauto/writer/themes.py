"""HTML/CSS resume and cover-letter templates for writer v2.

Each theme is a self-contained stylesheet over one shared semantic document,
so every theme extracts to the same ATS reading order: header, then sections
in DOM order.  No theme uses tables, icons, skill bars, images or text in
pseudo-elements that carries meaning.

Pagination is left to Chromium's print engine (``@page`` with margin boxes).
Entries may split between bullets (keeping whole entries together leaves a
third of page one empty); a heading never ends a page and a bullet never splits.  ``resume.page_break_before`` lets the
writer force a clean page-2 start when a theme would otherwise split badly.
"""
from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..pdf import house_style_font_dir


def _e(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


@dataclass(frozen=True)
class Theme:
    key: str
    label: str
    description: str
    header: str  # "left" | "center" | "band" | "rail"
    css: str


def _karla_faces() -> str:
    font_dir = house_style_font_dir()
    faces = []
    for weight, name, style in ((400, "Karla-Regular.ttf", "normal"), (500, "Karla-Medium.ttf", "normal"),
                                (600, "Karla-SemiBold.ttf", "normal"), (700, "Karla-Bold.ttf", "normal"),
                                (400, "Karla-Italic.ttf", "italic")):
        faces.append(f"@font-face {{ font-family: 'Karla'; src: url('{(font_dir / name).as_uri()}') "
                     f"format('truetype'); font-weight: {weight}; font-style: {style}; }}")
    return "\n".join(faces)


_BASE = """
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #fff; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { color: var(--ink); font-family: var(--body-font); font-size: var(--body-size); line-height: var(--leading);
  font-kerning: normal; text-rendering: optimizeLegibility; hyphens: manual; }
a { color: inherit; text-decoration: none; }
h1, h2, h3, p, ul { margin: 0; padding: 0; }
.contact span { white-space: nowrap; }
section { margin-top: var(--section-gap); }
section.first { margin-top: 0; }
h2 { break-after: avoid; page-break-after: avoid; }
.entry { margin-bottom: var(--entry-gap); }
.entry.keep { break-inside: avoid; page-break-inside: avoid; }
.entry-head, .entry-sub { break-after: avoid; page-break-after: avoid; }
ul.bullets li, .skills-row { break-inside: avoid; page-break-inside: avoid; }
.entry:last-child { margin-bottom: 0; }
.entry-head { display: flex; justify-content: space-between; align-items: baseline; gap: 4mm; }
.entry-head .when { white-space: nowrap; color: var(--muted); font-size: var(--meta-size); font-variant-numeric: tabular-nums; }
.entry-sub { display: flex; justify-content: space-between; gap: 4mm; color: var(--muted); font-size: var(--meta-size); }
/* Native list markers only: a positioned ::before bullet makes Chromium paint
   every list item after all unpositioned text, which scrambles PDF reading order. */
ul.bullets { list-style: disc outside; margin-top: 1.1mm; padding-left: 4.2mm; }
ul.bullets li { margin-bottom: 0.6mm; padding-left: 0.6mm; }
ul.bullets li::marker { color: var(--bullet); font-size: 0.9em; }
.skills-row { display: grid; grid-template-columns: var(--skill-label-w) 1fr; column-gap: 3mm; margin-bottom: 1mm; }
.skills-row .label { font-weight: 700; color: var(--accent-ink); }
.pub { margin-bottom: 1.2mm; break-inside: avoid; }
.pub .pub-title { font-weight: 600; }
.pub .pub-meta { color: var(--muted); font-size: var(--meta-size); }
.force-break { break-before: page; page-break-before: always; }
/* letter */
.letter-page .letter-body { font-size: var(--letter-size, 10.8pt); line-height: 1.42; }
.letter-body p { margin-bottom: 3.4mm; }
.letter-meta { display: flex; justify-content: space-between; align-items: flex-end; gap: 6mm; margin-bottom: 6mm; }
.recipient { line-height: 1.35; }
.letter-date { white-space: nowrap; color: var(--muted); }
.letter-subject { font-weight: 700; margin-bottom: 5mm; color: var(--accent-ink); }
.salutation { margin-bottom: 3.2mm; }
.closing { margin-top: 5mm; }
.signature { margin-top: 8mm; font-weight: 700; }
"""


THEMES: dict[str, Theme] = {}


def _register(theme: Theme) -> None:
    THEMES[theme.key] = theme


_register(Theme(
    key="karla-navy",
    label="Karla Navy",
    description="The project's house style refined: Karla, navy headings with a hairline rule, dates flush right.",
    header="left",
    css="""
:root { --ink:#1f2328; --muted:#5b6270; --accent:#253A5E; --accent-ink:#253A5E; --bullet:#253A5E;
  --body-font:'Karla', 'Segoe UI', Arial, sans-serif; --body-size:10pt; --leading:1.3; --meta-size:9.2pt;
  --section-gap:3.8mm; --entry-gap:2.6mm; --skill-label-w:43mm; }
@page { size: A4; margin: 13mm 16mm 14mm;
  @bottom-right { content: counter(page) " / " counter(pages); font-family: 'Karla', sans-serif; font-size: 8.5pt; color: #5b6270; }
  @bottom-left { content: "__NAME__"; font-family: 'Karla', sans-serif; font-size: 8.5pt; color: #5b6270; } }
header.masthead { display: block;
  padding-bottom: 3.2mm; border-bottom: 1.4pt solid var(--accent); margin-bottom: 4.4mm; }
header h1 { font-size: 23pt; line-height: 1.05; font-weight: 700; letter-spacing: -0.2pt; color: #14213a; }
header .headline { margin-top: 1.6mm; color: var(--accent); font-weight: 600; font-size: 10.6pt; }
header .contact { margin-top: 1.8mm; color: var(--muted); font-size: 9pt; }
header .contact span + span::before { content: "|"; margin: 0 2.2mm; color: #9aa3b2; }
h2 { font-size: 10.4pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.9pt; color: var(--accent);
  padding-bottom: 1mm; border-bottom: 0.5pt solid #c9d0db; margin-bottom: 2.2mm; }
.entry-head .role { font-weight: 700; color: #14213a; font-size: 10.4pt; }
.entry-sub .org { font-weight: 600; color: #3c4658; }
.summary p { color: #262b33; }
.letter-page header.masthead { margin-bottom: 9mm; }
""",
))

_register(Theme(
    key="scholar-serif",
    label="Scholar Serif",
    description="Academic serif for thesis and research roles: centred small-caps name, ruled small-caps headings, burgundy accent.",
    header="center",
    css="""
:root { --ink:#1b1b1b; --muted:#555; --accent:#7a2432; --accent-ink:#1b1b1b; --bullet:#7a2432;
  --body-font:Cambria, 'Cambria Math', Georgia, 'Times New Roman', serif; --body-size:10.5pt; --leading:1.3;
  --meta-size:9.6pt; --section-gap:4.2mm; --entry-gap:2.8mm; --skill-label-w:45mm; }
@page { size: A4; margin: 13mm 17mm 15mm;
  @bottom-center { content: "__NAME__  |  " counter(page) " of " counter(pages); font-family: Cambria, Georgia, serif; font-size: 8.8pt; color: #555; } }
header.masthead { text-align: center; margin-bottom: 4mm; }
header h1 { font-size: 24pt; font-weight: 400; font-variant: small-caps; letter-spacing: 1.2pt; line-height: 1.05; }
header .headline { margin-top: 1.4mm; font-style: italic; color: var(--accent); font-size: 11pt; }
header .contact { margin-top: 1.8mm; color: var(--muted); font-size: 9.6pt; }
header .contact span + span::before { content: "\\00B7"; margin: 0 2.4mm; color: #999; }
h2 { font-size: 12pt; font-weight: 400; font-variant: small-caps; letter-spacing: 0.9pt; color: var(--accent);
  border-bottom: 0.7pt solid #1b1b1b; padding-bottom: 0.6mm; margin-bottom: 2mm; }
.entry-head .role { font-weight: 700; }
.entry-sub .org { font-style: italic; color: #333; }
.skills-row .label { color: #1b1b1b; }
.pub .pub-title { font-style: italic; font-weight: 400; }
""",
))

_register(Theme(
    key="margin-rail",
    label="Margin Rail",
    description="Engineering layout with section labels in a left rail and content in a ruled right column; teal accent, Segoe UI.",
    header="rail",
    css="""
:root { --ink:#20262d; --muted:#5f6b76; --accent:#0e6b70; --accent-ink:#0e6b70; --bullet:#0e6b70;
  --body-font:'Segoe UI', 'Karla', Arial, sans-serif; --body-size:9.9pt; --leading:1.33; --meta-size:8.9pt;
  --section-gap:3.6mm; --entry-gap:2.5mm; --skill-label-w:43mm; --rail:25mm; }
@page { size: A4; margin: 13mm 15mm 15mm;
  @bottom-right { content: counter(page) " / " counter(pages); font-family: 'Segoe UI', sans-serif; font-size: 8pt; color: #5f6b76; } }
header.masthead { padding-left: 5mm; border-left: 2.2mm solid var(--accent); margin-bottom: 5mm; }
header h1 { font-size: 22pt; font-weight: 600; letter-spacing: -0.3pt; line-height: 1.05; color: #111820; }
header .headline { margin-top: 1.2mm; color: var(--accent); font-weight: 600; font-size: 10.4pt; }
header .contact { margin-top: 1.6mm; color: var(--muted); font-size: 8.9pt; display: flex; flex-wrap: wrap; gap: 0 4mm; }
/* Absolute rail labels instead of a grid: Chromium moves a grid row with unbreakable entries whole. */
section { position: relative; padding-left: calc(var(--rail) + 5mm); }
section > h2 { position: absolute; left: 0; top: 0; width: var(--rail); text-align: right; font-size: 8.2pt; font-weight: 700; text-transform: uppercase; letter-spacing: 0.4pt;
  color: var(--accent); padding-top: 0.5mm; line-height: 1.3; white-space: nowrap; }
section > .sec-body { border-left: 0.8pt solid #cfd8dc; padding-left: 4.5mm; }
.entry-head .role { font-weight: 700; color: #111820; }
.entry-sub .org { font-weight: 600; color: #37424d; }
.letter-page header.masthead { margin-bottom: 8mm; }
""",
))

_register(Theme(
    key="slate-band",
    label="Slate Band",
    description="Modern industry layout: dark slate masthead band on page one, copper section markers, Karla body.",
    header="band",
    css="""
:root { --ink:#22272e; --muted:#5d6570; --accent:#b0612b; --accent-ink:#2e3a4b; --bullet:#b0612b;
  --body-font:'Karla', 'Segoe UI', Arial, sans-serif; --body-size:10pt; --leading:1.3; --meta-size:9.1pt;
  --section-gap:3.8mm; --entry-gap:2.6mm; --letter-size:10.5pt; --skill-label-w:43mm; }
@page { size: A4; margin: 14mm 0 15mm;
  @bottom-right { content: counter(page) " / " counter(pages); font-family: 'Karla', sans-serif; font-size: 8.4pt; color: #5d6570; padding-right: 16mm; } }
@page :first { margin-top: 0; }
body { padding: 0 16mm; }
header.masthead { background: #2e3a4b; color: #fff; margin: 0 -16mm 4.5mm; padding: 8.5mm 16mm 6mm;
  border-bottom: 1.6mm solid var(--accent); }
header h1 { font-size: 24pt; font-weight: 700; letter-spacing: 0.2pt; line-height: 1.05; }
header .headline { margin-top: 1.8mm; color: #f0c9a8; font-weight: 600; font-size: 10.8pt; }
header .contact { margin-top: 2.6mm; font-size: 8.9pt; color: #dfe5ec; display: flex; flex-wrap: nowrap; justify-content: space-between; gap: 0 3mm; }
h2 { font-size: 10.6pt; font-weight: 700; color: var(--accent-ink); text-transform: uppercase; letter-spacing: 0.8pt;
  margin-bottom: 2mm; display: flex; align-items: center; gap: 2.4mm; }
h2::before { content: ""; width: 5mm; height: 1.6pt; background: var(--accent); display: inline-block; }
.entry-head .role { font-weight: 700; color: #1b2430; font-size: 10.3pt; }
.entry-sub .org { font-weight: 600; color: var(--accent); }
.letter-page header.masthead { margin-bottom: 7mm; }
""",
))


# ---------------------------------------------------------------------------
# document assembly
# ---------------------------------------------------------------------------

def _dates(entry: dict[str, Any]) -> str:
    start, end = entry.get("start", ""), entry.get("end", "")
    if start and end:
        return f"{start} - {end}"
    return str(start or end or entry.get("date", ""))


def _contact(candidate: dict[str, Any]) -> str:
    items = [candidate.get(k) for k in ("location", "phone", "email", "linkedin")]
    return "".join(f"<span>{_e(v)}</span>" for v in items if v)


def _masthead(theme: Theme, candidate: dict[str, Any]) -> str:
    ident = (f'<h1>{_e(candidate["name"])}</h1>'
             f'<p class="headline">{_e(candidate.get("headline", ""))}</p>')
    if theme.header == "left":
        return f'<header class="masthead"><div>{ident}</div><p class="contact">{_contact(candidate)}</p></header>'
    if theme.header == "rail":
        return f'<header class="masthead"><div>{ident}<p class="contact">{_contact(candidate)}</p></div></header>'
    return f'<header class="masthead">{ident}<p class="contact">{_contact(candidate)}</p></header>'


def _entry(entry: dict[str, Any], *, title_key: str = "title") -> str:
    title = entry.get(title_key) or entry.get("name", "")
    org = ", ".join(x for x in (entry.get("org"), entry.get("location")) if x)
    bullets = "".join(f"<li>{_e(b)}</li>" for b in entry.get("bullets", []))
    # Short entries stay whole; longer ones may split between bullets to avoid page-one gaps.
    cls = "entry keep" if len(entry.get("bullets", [])) <= 3 else "entry"
    return (f'<article class="{cls}"><div class="entry-head"><span class="role">{_e(title)}</span>'
            f'<span class="when">{_e(_dates(entry))}</span></div>'
            f'<div class="entry-sub"><span class="org">{_e(org)}</span></div>'
            f'<ul class="bullets">{bullets}</ul></article>')


def _education(entry: dict[str, Any]) -> str:
    org = ", ".join(x for x in (entry.get("institution"), entry.get("location")) if x)
    details = "".join(f"<li>{_e(d)}</li>" for d in entry.get("details", []))
    body = f'<ul class="bullets">{details}</ul>' if details else ""
    return (f'<article class="entry"><div class="entry-head"><span class="role">{_e(entry.get("degree"))}</span>'
            f'<span class="when">{_e(_dates(entry))}</span></div>'
            f'<div class="entry-sub"><span class="org">{_e(org)}</span></div>{body}</article>')


DEFAULT_ORDER = ("summary", "experience", "projects", "education", "skills", "publications", "languages")
SECTION_TITLES = {"summary": "Profile", "experience": "Experience", "projects": "Projects",
                  "education": "Education", "skills": "Skills", "publications": "Publications",
                  "languages": "Languages"}


def _section_body(key: str, resume: dict[str, Any], break_entry: tuple[str, int] | None) -> str:
    if key == "summary":
        return f"<p>{_e(resume.get('summary'))}</p>"
    if key in ("experience", "projects"):
        parts = []
        for i, entry in enumerate(resume.get(key, [])):
            block = _entry(entry, title_key="title" if key == "experience" else "name")
            if break_entry == (key, i):
                block = block.replace('<article class="entry', '<article class="force-break entry', 1)
            parts.append(block)
        return "".join(parts)
    if key == "education":
        return "".join(_education(e) for e in resume.get("education", []))
    if key == "skills":
        rows = list(resume.get("skills", []))
        if resume.get("languages"):  # one row instead of a separate section heading
            rows.append({"label": "Languages", "items": resume["languages"]})
        return "".join(f'<div class="skills-row"><span class="label">{_e(r.get("label"))}</span>'
                       f'<span>{_e(r.get("items"))}</span></div>' for r in rows)
    if key == "publications":
        rows = []
        for pub in resume.get("publications", []):
            meta = ", ".join(x for x in (pub.get("venue"), pub.get("status"), pub.get("date")) if x)
            rows.append(f'<div class="pub"><div class="pub-title">{_e(pub.get("title"))}</div>'
                        f'<div class="pub-meta">{_e(meta)}</div></div>')
        return "".join(rows)
    if key == "languages":
        return f"<p>{_e(resume.get('languages'))}</p>"
    raise KeyError(key)


def _present(key: str, resume: dict[str, Any]) -> bool:
    if key == "languages" and resume.get("skills"):
        return False  # rendered as the last skills row
    return bool(resume.get(key))


_LETTER_PAGE = ("@page { @bottom-left { content: none; } @bottom-center { content: none; } "
                "@bottom-right { content: none; } }")


def _page(theme: Theme, title: str, body: str, extra_class: str = "", *, name: str = "") -> str:
    css = theme.css.replace("__NAME__", name.replace('"', "'"))
    if extra_class == "letter-page":
        css += _LETTER_PAGE
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{_e(title)}</title>'
            f"<style>{_karla_faces()}{_BASE}{css}</style></head>"
            f'<body class="theme-{theme.key} {extra_class}">{body}</body></html>')


def render_resume(content: dict[str, Any], theme_key: str) -> str:
    theme = THEMES[theme_key]
    candidate, resume = content["candidate"], content["resume"]
    order = [k for k in resume.get("section_order", DEFAULT_ORDER) if _present(k, resume)]
    brk = str(resume.get("page_break_before", ""))
    break_section, break_entry = None, None
    if ":" in brk:
        name, index = brk.split(":", 1)
        break_entry = (name, int(index))
    elif brk:
        break_section = brk
    sections = []
    for i, key in enumerate(order):
        classes = [key] + (["first"] if i == 0 else []) + (["force-break"] if key == break_section else [])
        sections.append(f'<section class="{" ".join(classes)}"><h2>{_e(SECTION_TITLES[key])}</h2>'
                        f'<div class="sec-body">{_section_body(key, resume, break_entry)}</div></section>')
    title = f"{candidate['name']} - Resume - {content.get('job', {}).get('company', '')}"
    return _page(theme, title, _masthead(theme, candidate) + "".join(sections), "resume-page",
                 name=candidate.get("preferred_name") or candidate["name"])


def render_letter(content: dict[str, Any], theme_key: str) -> str:
    theme = THEMES[theme_key]
    candidate, letter = content["candidate"], content["cover_letter"]
    recipient = "<br>".join(_e(line) for line in letter.get("recipient_lines", []))
    paragraphs = "".join(f"<p>{_e(p)}</p>" for p in letter.get("paragraphs", []))
    body = (f'<div class="letter-meta"><div class="recipient">{recipient}</div>'
            f'<div class="letter-date">{_e(letter.get("date", ""))}</div></div>'
            f'<p class="letter-subject">{_e(letter.get("subject", ""))}</p>'
            f'<div class="letter-body"><p class="salutation">{_e(letter.get("salutation", "Dear Hiring Team,"))}</p>'
            f'{paragraphs}<p class="closing">{_e(letter.get("closing", "Kind regards,"))}</p>'
            f'<p class="signature">{_e(letter.get("signature") or candidate.get("preferred_name") or candidate["name"])}</p></div>')
    title = f"{candidate['name']} - Cover Letter - {content.get('job', {}).get('company', '')}"
    return _page(theme, title, _masthead(theme, candidate) + body, "letter-page",
                 name=candidate.get("preferred_name") or candidate["name"])


def write_theme_files(content: dict[str, Any], theme_key: str, out_dir: Path) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    resume_html = out_dir / "resume.html"
    letter_html = out_dir / "cover_letter.html"
    resume_html.write_text(render_resume(content, theme_key), encoding="utf-8")
    letter_html.write_text(render_letter(content, theme_key), encoding="utf-8")
    return {"resume_html": resume_html, "cover_letter_html": letter_html}
