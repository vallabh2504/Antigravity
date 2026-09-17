"""Render writer v2 content through every requested template and QA each PDF."""
from __future__ import annotations

import html
import json
import os
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any

from ..pdf import check_reading_order, export_pdf, find_browser, set_pdf_metadata
from . import rendercv_engine, themes
from .facts import FactCorpus, errors, load_fact_corpus, validate_writer_content

_TRANSLIT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"})


def _long(path: Path) -> str:
    """Extended-length form so copies survive Windows' 260-character limit."""
    text = str(Path(path).resolve())
    if os.name == "nt" and not text.startswith("\\\\?\\"):
        return "\\\\?\\" + text
    return text


def find_pdftoppm() -> Path | None:
    """Poppler's pdftoppm, which draws the page images the reviewer looks at."""
    override = os.environ.get("JOBAUTO_PDFTOPPM", "").strip()
    if override and Path(override).is_file():
        return Path(override)
    found = shutil.which("pdftoppm")
    return Path(found) if found else None


def _qa(pdf: Path, *, pages: int, content: dict[str, Any], kind: str) -> dict[str, Any]:
    from pypdf import PdfReader


    reader = PdfReader(str(pdf))
    problems: list[str] = []
    if len(reader.pages) != pages:
        problems.append(f"{kind}: expected {pages} page(s), found {len(reader.pages)}")
    for i, page in enumerate(reader.pages, 1):
        w, h = float(page.mediabox.width), float(page.mediabox.height)
        if abs(w - 595.28) > 2 or abs(h - 841.89) > 2:
            problems.append(f"{kind}: page {i} is not A4 ({w:.0f}x{h:.0f}pt)")
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    candidate = content["candidate"]
    for token in (candidate.get("email", ""), (candidate.get("name") or " ").split()[-1]):
        if token and token not in text:
            problems.append(f"{kind}: {token!r} not extractable")
    if "�" in text:
        problems.append(f"{kind}: replacement character in extracted text")
    # Last page should carry real content, not a two-line spill.
    if len(reader.pages) >= 2:
        last_chars = len(re.sub(r"\s+", "", reader.pages[-1].extract_text() or ""))
        if kind == "resume" and last_chars < 900:
            problems.append(f"resume: last page is nearly empty ({last_chars} chars); add relevant content")
    if kind == "cover_letter" and len(reader.pages) > 1:
        from .facts import words
        count = sum(words(p) for p in content["cover_letter"].get("paragraphs", []))
        problems.append(f"cover_letter: {count} words do not fit one page in this template; "
                        f"cut to about {max(340, count - 40)} words")
    report: dict[str, Any] = {"pdf": str(pdf), "pages": len(reader.pages), "problems": problems}
    if kind == "resume":
        # The role title anchors each entry: employer names also occur in the summary.
        roles = [{"employer": e["title"], "dates": "",
                  "bullets": [" ".join(re.split(r"['’]", b)[0].split()[:6]) for b in e.get("bullets", [])]}
                 for e in content["resume"].get("experience", [])]
        order = check_reading_order(pdf, roles, contacts=[candidate["email"]])
        report["reading_order"] = {"ok": order["ok"], "failures": order["failures"][:8],
                                   "similarity": order["extractor_similarity"]}
        if not order["ok"]:
            problems.append("resume: reading-order check failed: " + "; ".join(order["failures"][:3]))
    return report


def _previews(pdf: Path, out: Path, dpi: int) -> list[str]:
    exe = find_pdftoppm()
    if exe is None:
        return []
    import subprocess

    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob(f"{pdf.stem}-*.png"):
        old.unlink()
    # Relative paths from inside the preview folder keep long application paths under the limit.
    subprocess.run([str(exe), "-png", "-r", str(dpi), os.path.relpath(pdf, out), pdf.stem],
                   cwd=out, capture_output=True, timeout=120)
    return [str(p) for p in sorted(out.glob(f"{pdf.stem}-*.png"))]


def _ascii(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text).translate(_TRANSLIT))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _upload_names(content: dict[str, Any], job: dict[str, Any]) -> tuple[str, str]:
    person = content["candidate"].get("preferred_name") or content["candidate"]["name"]
    name = re.sub(r"[^A-Za-z0-9]+", "_", _ascii(person)).strip("_")
    raw = re.sub(r"\s+(?:gmbh|ag|se|inc|ltd|limited|llc|kg|mbh)\.?$", "", str(job.get("company", "")).strip(), flags=re.I)
    company = re.sub(r"[^A-Za-z0-9]+", "_", _ascii(raw)).strip("_")[:60].strip("_") or "Application"
    return f"{name}_Resume_{company}.pdf", f"{name}_Cover_Letter_{company}.pdf"


def render_suite(content: dict[str, Any], job: dict[str, Any], out_root: str | Path, *,
                 html_themes: list[str] | None = None, rendercv_themes: list[str] | None = None,
                 corpus: FactCorpus | None = None, allow_errors: bool = False,
                 preview_dpi: int = 110) -> dict[str, Any]:
    """Validate once, then render and QA every template.  Returns the run report."""
    out_root = Path(out_root).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    findings = validate_writer_content(content, job, corpus or load_fact_corpus())
    report: dict[str, Any] = {"validation": [f.as_dict() for f in findings], "templates": []}
    if errors(findings) and not allow_errors:
        report["status"] = "validation_failed"
        (out_root / "render_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report

    candidate = content["candidate"]
    company = job.get("company", "")
    role = job.get("title", "")
    resume_upload, letter_upload = _upload_names(content, job)
    browser = find_browser()

    jobs: list[tuple[str, str]] = [("html", t) for t in (html_themes if html_themes is not None else list(themes.THEMES))]
    jobs += [("rendercv", t) for t in (rendercv_themes if rendercv_themes is not None
                                       else list(rendercv_engine.DEFAULT_THEMES))]
    for engine, theme in jobs:
        tdir = out_root / f"{engine}-{theme}"
        entry: dict[str, Any] = {"engine": engine, "theme": theme, "dir": str(tdir)}
        try:
            if engine == "html":
                files = themes.write_theme_files(content, theme, tdir)
                resume_pdf = export_pdf(files["resume_html"], tdir / "resume.pdf", browser)
                letter_pdf = export_pdf(files["cover_letter_html"], tdir / "cover_letter.pdf", browser)
                entry["label"] = themes.THEMES[theme].label
                entry["description"] = themes.THEMES[theme].description
            else:
                files = rendercv_engine.render_rendercv(content, theme, tdir)
                resume_pdf, letter_pdf = files["resume_pdf"], files["cover_letter_pdf"]
                entry["label"] = f"rendercv {theme}"
                entry["description"] = f"rendercv built-in '{theme}' theme (Typst), with a matching Typst cover letter."
            set_pdf_metadata(resume_pdf, title=f"{candidate['name']} - Resume - {company}",
                             author=candidate["name"], subject=f"Application for {role}")
            set_pdf_metadata(letter_pdf, title=f"{candidate['name']} - Cover Letter - {company}",
                             author=candidate["name"], subject=f"Application for {role}")
            shutil.copy2(_long(resume_pdf), _long(tdir / resume_upload))
            shutil.copy2(_long(letter_pdf), _long(tdir / letter_upload))
            entry["resume"] = _qa(resume_pdf, pages=int(content["resume"].get("pages", 2)), content=content, kind="resume")
            entry["cover_letter"] = _qa(letter_pdf, pages=1, content=content, kind="cover_letter")
            entry["previews"] = (_previews(resume_pdf, tdir / "preview", preview_dpi)
                                 + _previews(letter_pdf, tdir / "preview", preview_dpi))
            entry["ok"] = not (entry["resume"]["problems"] or entry["cover_letter"]["problems"])
        except Exception as exc:  # one broken template must not hide the others
            entry["ok"] = False
            entry["error"] = f"{type(exc).__name__}: {exc}"
        report["templates"].append(entry)
    report["status"] = "ok" if all(t["ok"] for t in report["templates"]) and not errors(findings) else "problems"
    (out_root / "render_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_gallery(out_root, report, job)
    return report


def write_gallery(out_root: Path, report: dict[str, Any], job: dict[str, Any]) -> Path:
    """A local page to compare templates side by side (never published)."""
    cards = []
    for t in report["templates"]:
        rel = lambda p: Path(p).relative_to(out_root).as_posix()  # noqa: E731
        imgs = "".join(f'<img src="{html.escape(rel(p))}" loading="lazy">' for p in t.get("previews", []))
        status = "pass" if t.get("ok") else "check"
        problems = [*t.get("resume", {}).get("problems", []), *t.get("cover_letter", {}).get("problems", [])]
        if t.get("error"):
            problems.append(t["error"])
        plist = "".join(f"<li>{html.escape(p)}</li>" for p in problems)
        links = ""
        if t.get("resume"):
            links = (f'<a href="{html.escape(rel(t["resume"]["pdf"]))}">resume.pdf</a> '
                     f'<a href="{html.escape(rel(t["cover_letter"]["pdf"]))}">cover_letter.pdf</a>')
        cards.append(f'<section><h2>{html.escape(t.get("label", t["theme"]))} <small class="{status}">{status}</small></h2>'
                     f'<p>{html.escape(t.get("description", ""))}</p><p>{links}</p><ul>{plist}</ul>'
                     f'<div class="strip">{imgs}</div></section>')
    page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Template gallery</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f3f4f6;color:#1f2328}}
section{{background:#fff;border-radius:8px;padding:16px 20px;margin:0 0 20px;box-shadow:0 1px 3px #0002}}
h2{{margin:0 0 4px;font-size:18px}} small{{font-size:12px;padding:2px 8px;border-radius:10px}}
.pass{{background:#dcfce7;color:#166534}} .check{{background:#fee2e2;color:#991b1b}}
.strip{{display:flex;gap:12px;overflow-x:auto}} .strip img{{height:520px;border:1px solid #d1d5db}}
a{{margin-right:12px}}</style></head><body><h1>{html.escape(job.get('company', ''))}: {html.escape(job.get('title', ''))}</h1>
{''.join(cards)}</body></html>"""
    path = out_root / "gallery.html"
    path.write_text(page, encoding="utf-8")
    return path
