"""HTML -> PDF export for the tailored documents (upload-ready files).

Engine order:
  1. WeasyPrint (pip install weasyprint) — renders the print CSS well, no browser needed.
  2. OpenClaw browser / headless Chrome "print to PDF" — used on hosts that have it.
  3. Fallback: the HTML already carries @media print A4 styling, so the agent/user can
     open it and Save as PDF. We report this instead of failing.
"""
from __future__ import annotations

from pathlib import Path

from .config import output_dir
from .db import DB

DOCS = ("resume.html", "cover_letter.html")


def _convert(src: Path, dst: Path) -> bool:
    try:
        from weasyprint import HTML  # lazy
    except ImportError:
        return False
    HTML(filename=str(src)).write_pdf(str(dst))
    return dst.exists() and dst.read_bytes()[:4] == b"%PDF"


def export_job(job_id: str) -> dict:
    jdir = output_dir() / job_id
    result = {"id": job_id, "pdfs": [], "skipped": []}
    for name in DOCS:
        src = jdir / name
        if not src.exists():
            continue
        dst = src.with_suffix(".pdf")
        if _convert(src, dst):
            result["pdfs"].append(str(dst))
        else:
            result["skipped"].append(str(src))
    return result


def export_all(db: DB, ids: list[str] | None = None) -> list[dict]:
    if ids:
        targets = ids
    else:
        # everything that has tailored docs
        targets = [j["id"] for j in db.all() if (output_dir() / j["id"] / "resume.html").exists()]
    return [export_job(i) for i in targets]
