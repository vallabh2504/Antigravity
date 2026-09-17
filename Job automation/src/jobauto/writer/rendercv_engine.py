"""rendercv (Typst) templates for writer v2.

rendercv pins its own pydantic/typst stack, so it is never imported into the
jobauto interpreter.  It runs in a separate interpreter found by
:func:`find_rendercv_python`:

1. ``JOBAUTO_RENDERCV_PYTHON`` (path to a python executable);
2. ``<project>/.venv-rendercv`` (``python -m venv .venv-rendercv`` then
   ``pip install "rendercv[full]==2.8"``);
3. the current interpreter, when ``rendercv`` happens to be importable.

rendercv renders resumes only.  The matching cover letter is compiled with the
same Typst engine and fonts through a small template in this module, so each
rendercv option is still a matched pair.
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path
from typing import Any

import yaml
from pypdf import PdfReader

from .. import config

#: Themes offered by default, and the letter styling that matches each one.
LETTER_STYLES: dict[str, dict[str, str]] = {
    "classic": {"font": "Source Sans 3", "accent": "rgb(0, 79, 144)", "rule": "rgb(0, 79, 144)", "size": "10.6pt"},
    "engineeringresumes": {"font": "XCharter", "accent": "rgb(0, 0, 0)", "rule": "rgb(0, 0, 0)", "size": "10.8pt"},
    "harvard": {"font": "XCharter", "accent": "rgb(0, 0, 0)", "rule": "rgb(0, 0, 0)", "size": "10.8pt"},
    "sb2nov": {"font": "New Computer Modern", "accent": "rgb(0, 0, 0)", "rule": "rgb(0, 0, 0)", "size": "10.8pt"},
    "moderncv": {"font": "Fontin", "accent": "rgb(0, 79, 144)", "rule": "rgb(0, 79, 144)", "size": "10.6pt"},
    "engineeringclassic": {"font": "Raleway", "accent": "rgb(0, 79, 144)", "rule": "rgb(0, 79, 144)", "size": "10.2pt"},
    "ink": {"font": "Source Sans 3", "accent": "rgb(30, 30, 30)", "rule": "rgb(30, 30, 30)", "size": "10.6pt"},
    "opal": {"font": "Source Sans 3", "accent": "rgb(0, 79, 144)", "rule": "rgb(0, 79, 144)", "size": "10.6pt"},
    "ember": {"font": "Source Sans 3", "accent": "rgb(160, 60, 30)", "rule": "rgb(160, 60, 30)", "size": "10.6pt"},
}
#: harvard stays renderable on request; its degree column duplicates the degree text.
DEFAULT_THEMES = ("classic", "engineeringresumes", "sb2nov")

#: Per-theme density so every theme lands on two A4 pages with the same text.
_DENSITY: dict[str, dict[str, Any]] = {
    "classic": {"body": "10pt", "margin": "1.6cm", "top": "1.4cm", "entries": "0.34cm"},
    "engineeringresumes": {"body": "10pt", "margin": "1.6cm", "top": "1.4cm", "entries": "0.3cm"},
    "harvard": {"body": "10pt", "margin": "1.6cm", "top": "1.3cm", "entries": "0.3cm"},
    "sb2nov": {"body": "10pt", "margin": "1.6cm", "top": "1.4cm", "entries": "0.3cm"},
}


def find_rendercv_python() -> Path | None:
    override = os.environ.get("JOBAUTO_RENDERCV_PYTHON", "").strip()
    if override and Path(override).is_file():
        return Path(override)
    for base in (config.project_root(), config.CHECKOUT_DIR):
        for rel in ("Scripts/python.exe", "bin/python"):
            candidate = base / ".venv-rendercv" / rel
            if candidate.is_file():
                return candidate
    if importlib.util.find_spec("rendercv") is not None:
        return Path(sys.executable)
    return None


def _ym(value: str) -> str:
    value = str(value or "").strip()
    if value.lower() in {"present", "today", "now"}:
        return "present"
    match = re.fullmatch(r"(\d{1,2})/(\d{4})", value)
    if match:
        return f"{match.group(2)}-{int(match.group(1)):02d}"
    return value


def _md(text: Any) -> str:
    """Escape rendercv markdown control characters in plain prose."""
    return re.sub(r"([*_`\[\]#])", r"\\\1", str(text or ""))


def _templates(theme: str) -> dict[str, Any]:
    """Shared entry layout: the date sits alone in the right column so extractors keep it on the title line."""
    date = "*DATE*" if theme == "sb2nov" else "DATE"
    # classic's right column extracts after the bullets, so parsers would pin the date to the next role.
    inline = " | DATE" if theme == "classic" else ""
    column = "" if inline else date
    return {
        "footer": "*NAME | PAGE_NUMBER of TOTAL_PAGES*",
        "single_date": "MONTH_IN_TWO_DIGITS/YEAR",
        "date_range": "START_DATE - END_DATE",
        "experience_entry": {"main_column": f"**POSITION**{inline}\nCOMPANY, LOCATION\nSUMMARY\nHIGHLIGHTS",
                             "date_and_location_column": column},
        "education_entry": {"main_column": f"**AREA**{inline}\nINSTITUTION, LOCATION\nSUMMARY\nHIGHLIGHTS",
                            "degree_column": None, "date_and_location_column": column},
        "normal_entry": {"main_column": f"**NAME**{inline}\nLOCATION\nSUMMARY\nHIGHLIGHTS",
                         "date_and_location_column": column},
    }


def build_cv_yaml(content: dict[str, Any], theme: str) -> dict[str, Any]:
    candidate, resume = content["candidate"], content["resume"]
    sections: dict[str, Any] = {}
    if resume.get("summary"):
        sections["Profile"] = [_md(resume["summary"])]
    if resume.get("experience"):
        sections["Experience"] = [{
            "company": _md(e.get("org")), "position": _md(e.get("title")),
            "start_date": _ym(e.get("start")), "end_date": _ym(e.get("end")),
            "location": _md(e.get("location")), "highlights": [_md(b) for b in e.get("bullets", [])],
        } for e in resume["experience"]]
    if resume.get("projects"):
        sections["Selected Projects"] = [{
            "name": _md(p.get("name")), "location": _md(p.get("org")),
            "start_date": _ym(p.get("start")), "end_date": _ym(p.get("end")),
            "highlights": [_md(b) for b in p.get("bullets", [])],
        } for p in resume["projects"]]
    if resume.get("education"):
        sections["Education"] = [{
            "institution": _md(e.get("institution")), "area": _md(e.get("degree")),
            "start_date": _ym(e.get("start")), "end_date": _ym(e.get("end")),
            "location": _md(e.get("location")), "highlights": [_md(d) for d in e.get("details", [])],
        } for e in resume["education"]]
    if resume.get("skills"):
        rows = [{"label": _md(r.get("label")), "details": _md(r.get("items"))} for r in resume["skills"]]
        if resume.get("languages"):
            rows.append({"label": "Languages", "details": _md(resume["languages"])})
        sections["Technical Skills"] = rows
    if resume.get("publications"):
        # Text entries: a manuscript in preparation has no date, so a date column would sit empty.
        sections["Publications"] = [
            f"**{_md(p.get('title'))}**, " + _md(", ".join(x for x in (p.get("venue"), p.get("status"), p.get("date")) if x))
            for p in resume["publications"]]
    cv: dict[str, Any] = {
        "name": candidate["name"], "headline": candidate.get("headline"),
        "location": candidate.get("location"), "email": candidate.get("email"),
        "phone": re.sub(r"\s+", "", candidate.get("phone", "")) or None,
        "sections": sections,
    }
    linkedin = str(candidate.get("linkedin", ""))
    if "linkedin.com/in/" in linkedin:
        cv["social_networks"] = [{"network": "LinkedIn", "username": linkedin.rstrip("/").split("/in/")[-1]}]
    density = _DENSITY.get(theme, _DENSITY["classic"])
    design: dict[str, Any] = {
        "theme": theme,
        "page": {"size": "a4", "top_margin": density["top"], "bottom_margin": "1.4cm",
                 "left_margin": density["margin"], "right_margin": density["margin"], "show_top_note": False,
                 "show_footer": True},
        # Justified text hyphenates tool names (MAT-LAB) and places (Schwieberdin-gen).
        "typography": {"font_size": {"body": density["body"]}, "alignment": "left"},
        "templates": _templates(theme),
        # Icon glyphs extract as private-use characters and break ATS parsing.
        "header": {"connections": {"show_icons": False, "phone_number_format": "international",
                                   "display_urls_instead_of_usernames": True, "separator": "|"}},
        "sections": {"space_between_regular_entries": density["entries"], "show_time_spans_in": []},
        # Roles are capped at four bullets, so whole-entry moves stay small and no heading is orphaned.
        "entries": {"allow_page_break": False, **({"date_and_location_width": "0cm"} if theme == "classic" else {})},
    }
    return {
        "cv": cv, "design": design, "locale": {"language": "english", "present": "Present"},
        "settings": {"current_date": "today", "bold_keywords": [],
                     "pdf_title": f"{candidate['name']} - Resume - {content.get('job', {}).get('company', '')}"},
    }


# (point-size reduction, line leading, paragraph spacing, side margin, top/bottom margin)
LETTER_FIT_STEPS = [
    (0.0, "0.72em", "1.15em", "2.2cm", "1.8cm"),
    (0.4, "0.68em", "1.0em", "2.0cm", "1.6cm"),
    (0.8, "0.65em", "0.9em", "1.9cm", "1.5cm"),
    (1.2, "0.62em", "0.85em", "1.8cm", "1.4cm"),
]

_LETTER_TYP = r"""
#let d = json("letter.json")
#set document(title: d.title, author: d.name)
#set page(paper: "a4", margin: (x: eval(d.margin_x), top: eval(d.margin_y), bottom: eval(d.margin_y)))
#set text(font: d.font, size: eval(d.size), fill: rgb(20, 20, 20), lang: "en")
#set par(justify: false, leading: eval(d.leading), spacing: eval(d.spacing))
#let accent = eval(d.accent)
#text(size: 24pt, fill: accent, weight: "bold")[#d.name]
#v(-0.35em)
#text(size: 10.4pt, fill: accent)[#d.headline]
#v(-0.2em)
#text(size: 9.2pt, fill: rgb(80, 80, 80))[#d.contact.slice(0, calc.min(3, d.contact.len())).join("  |  ") #if d.contact.len() > 3 [\ #d.contact.slice(3).join("  |  ")]]
#v(-0.3em)
#line(length: 100%, stroke: 0.7pt + eval(d.rule))
#v(0.9em)
#grid(columns: (1fr, auto), align: (left + bottom, right + bottom),
  [#for l in d.recipient [#l \ ]], text(fill: rgb(80, 80, 80))[#d.date])
#v(0.5em)
#text(weight: "bold", fill: accent)[#d.subject]
#v(0.3em)
#d.salutation
#parbreak()
#for p in d.paragraphs [
  #p
  #parbreak()
]
#v(0.2em)
#d.closing
#v(1.4em)
#text(weight: "bold")[#d.signature]
"""

_COMPILE_LETTER = r"""
import pathlib, sys, typst, rendercv_fonts
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
fonts = pathlib.Path(rendercv_fonts.__file__).parent
paths = [str(p) for p in fonts.iterdir() if p.is_dir()] + [str(fonts)]
typst.compile(str(src), output=str(out), root=str(src.parent), font_paths=paths)
"""


def render_rendercv(content: dict[str, Any], theme: str, out_dir: Path,
                    python: Path | None = None) -> dict[str, Path]:
    python = python or find_rendercv_python()
    if python is None:
        raise RuntimeError("rendercv is not installed; create .venv-rendercv or set JOBAUTO_RENDERCV_PYTHON")
    out_dir.mkdir(parents=True, exist_ok=True)
    # rendercv and Typst write intermediate files next to the input; application
    # folders can exceed the Windows 260-character path limit, so work in a short temp dir.
    with tempfile.TemporaryDirectory(prefix="rcv-") as tmp:
        work = Path(tmp)
        _render_in(content, theme, work, python)
        for name in ("resume.rendercv.yaml", "resume.typ", "resume.pdf", "letter.json", "cover_letter.typ", "cover_letter.pdf"):
            if (work / name).is_file():
                shutil.copy2(work / name, out_dir / name)
    return {"resume_pdf": out_dir / "resume.pdf", "cover_letter_pdf": out_dir / "cover_letter.pdf",
            "resume_yaml": out_dir / "resume.rendercv.yaml"}


def _render_in(content: dict[str, Any], theme: str, out_dir: Path, python: Path) -> None:
    cv_yaml = out_dir / "resume.rendercv.yaml"
    cv_yaml.write_text(yaml.safe_dump(build_cv_yaml(content, theme), allow_unicode=True, sort_keys=False),
                       encoding="utf-8")
    resume_pdf = out_dir / "resume.pdf"
    resume_pdf.unlink(missing_ok=True)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    done = subprocess.run(
        [str(python), "-m", "rendercv", "render", cv_yaml.name, "--pdf-path", resume_pdf.name,
         "--typst-path", "resume.typ", "-nomd", "-nohtml", "-nopng", "--quiet"],
        cwd=out_dir, capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=240)
    if done.returncode != 0 or not resume_pdf.is_file():
        raise RuntimeError(f"rendercv failed for theme {theme}: {done.stdout[-1500:]} {done.stderr[-1500:]}")

    candidate, letter = content["candidate"], content["cover_letter"]
    style = LETTER_STYLES.get(theme, LETTER_STYLES["classic"])
    data = {
        "title": f"{candidate['name']} - Cover Letter - {content.get('job', {}).get('company', '')}",
        "name": candidate["name"], "headline": candidate.get("headline", ""),
        "contact": [v for v in (candidate.get("location"), candidate.get("phone"), candidate.get("email"),
                                candidate.get("linkedin")) if v],
        "recipient": letter.get("recipient_lines", []), "date": letter.get("date", ""),
        "subject": letter.get("subject", ""), "salutation": letter.get("salutation", "Dear Hiring Team,"),
        "paragraphs": letter.get("paragraphs", []), "closing": letter.get("closing", "Kind regards,"),
        "signature": letter.get("signature") or candidate.get("preferred_name") or candidate["name"],
        **style,
    }
    letter_typ = out_dir / "cover_letter.typ"
    letter_typ.write_text(_LETTER_TYP, encoding="utf-8")
    letter_pdf = out_dir / "cover_letter.pdf"
    # A letter in the word budget must fit one page in every theme: tighten type and spacing in
    # small steps until it does.  The last step is still comfortably readable.
    base = float(str(style["size"]).removesuffix("pt"))
    for size_drop, leading, spacing, margin_x, margin_y in LETTER_FIT_STEPS:
        data.update(size=f"{base - size_drop:.1f}pt", leading=leading, spacing=spacing,
                    margin_x=margin_x, margin_y=margin_y)
        (out_dir / "letter.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        letter_pdf.unlink(missing_ok=True)
        done = subprocess.run([str(python), "-c", _COMPILE_LETTER, str(letter_typ), str(letter_pdf)],
                              capture_output=True, text=True, encoding="utf-8", errors="replace", env=env,
                              timeout=120)
        if done.returncode != 0 or not letter_pdf.is_file():
            raise RuntimeError(f"Typst letter failed for theme {theme}: {done.stderr[-2000:]}")
        if len(PdfReader(str(letter_pdf)).pages) == 1:
            break
