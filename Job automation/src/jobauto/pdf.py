"""PDF helpers: browser export, metadata, text extraction and a reading-order check."""
from __future__ import annotations

import difflib
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Iterable

from . import config

BANNED_PHRASES = ("highly motivated", "seeking a position", "perfect fit", "ideal candidate",
                  "uniquely suited", "passionate about", "keen interest", "i am confident that",
                  "leverage my skill set", "synergy", "cutting-edge solutions", "profound interest",
                  "unique blend", "regardless of the outcome")

_FONTS = ("Karla-Regular.ttf", "Karla-Medium.ttf", "Karla-SemiBold.ttf", "Karla-Bold.ttf", "Karla-Italic.ttf")


def house_style_font_dir() -> Path:
    """The bundled Karla fonts used by the HTML templates."""
    candidate = config.skills_dir() / "house-style" / "assets" / "fonts"
    if all((candidate / name).is_file() for name in _FONTS):
        return candidate
    raise FileNotFoundError(f"Karla fonts are missing from {candidate}")


# --------------------------------------------------------------------------- export

def find_browser() -> Path | None:
    """An installed Chromium-family browser, used to print HTML templates to PDF."""
    for name in ("msedge", "chrome", "chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            return Path(found)
    known = (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
             r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
    return next((Path(p) for p in known if Path(p).exists()), None)


_SETTLE_TIMEOUT_S = 30.0
_SETTLE_QUIET_S = 0.4
_SETTLE_POLL_S = 0.1


def _await_browser_write(dst: Path, *, launched_at: float, stderr: str) -> None:
    """Wait until *dst* is a complete PDF written by this launch.

    On Windows the process Chromium returns from often hands printing to a
    browser process it does not own, so the exit code arrives before the file.
    Accept the file only when it is newer than the launch, ends with the PDF
    trailer, and has stopped growing.
    """
    deadline = time.monotonic() + _SETTLE_TIMEOUT_S
    size: int | None = None
    since = 0.0
    while time.monotonic() < deadline:
        try:
            stat = dst.stat()
        except FileNotFoundError:
            size = None
            time.sleep(_SETTLE_POLL_S)
            continue
        if stat.st_mtime < launched_at - 1.0:
            time.sleep(_SETTLE_POLL_S)
            continue
        if stat.st_size != size:
            size, since = stat.st_size, time.monotonic()
            time.sleep(_SETTLE_POLL_S)
            continue
        if time.monotonic() - since < _SETTLE_QUIET_S:
            time.sleep(_SETTLE_POLL_S)
            continue
        blob = dst.read_bytes()
        if blob[:4] == b"%PDF" and b"%%EOF" in blob[-2048:]:
            return
        size = None
        time.sleep(_SETTLE_POLL_S)
    raise RuntimeError(f"browser did not finish writing {dst} within {_SETTLE_TIMEOUT_S:.0f}s: {stderr.strip()}")


def export_pdf(html_path: str | Path, pdf_path: str | Path, browser: str | Path | None = None) -> Path:
    src, dst = Path(html_path).resolve(), Path(pdf_path).resolve()
    executable = Path(browser) if browser else find_browser()
    if not executable or not executable.exists():
        raise RuntimeError("no Chrome, Chromium or Microsoft Edge executable was found")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.unlink(missing_ok=True)
    command = [str(executable), "--headless", "--disable-gpu", "--allow-file-access-from-files",
               "--no-pdf-header-footer", "--print-to-pdf-no-header", f"--print-to-pdf={dst}", src.as_uri()]
    launched_at = time.time()
    done = subprocess.run(command, capture_output=True, text=True, timeout=90, check=False)
    if done.returncode != 0:
        raise RuntimeError(f"browser PDF export failed ({done.returncode}): {done.stderr.strip()}")
    _await_browser_write(dst, launched_at=launched_at, stderr=done.stderr)
    return dst


def set_pdf_metadata(pdf_path: str | Path, *, title: str, author: str, subject: str) -> Path:
    from pypdf import PdfReader, PdfWriter

    path = Path(pdf_path)
    reader = PdfReader(str(path))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.add_metadata({"/Title": title, "/Author": author, "/Subject": subject})
    temp = path.with_suffix(".metadata.pdf")
    with temp.open("wb") as handle:
        writer.write(handle)
    temp.replace(path)
    return path


# ------------------------------------------------------------------------ extraction

def normalise_text(text: str) -> str:
    """NFKC, ligatures and line-break hyphenation joined, bullets dropped, whitespace collapsed."""
    text = text.replace("\u00ad", "")
    for ligature, plain in (("\ufb00", "ff"), ("\ufb01", "fi"), ("\ufb02", "fl"), ("\ufb03", "ffi"),
                            ("\ufb04", "ffl"), ("\ufb05", "st"), ("\ufb06", "st")):
        text = text.replace(ligature, plain)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"(\w)-\s*(?:\ufffd|[\u2022\u25aa\u25cf\u00b7\u2043\u2219])\s*(\w)", r"\1\2", text)
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"(\w)-\s+(?=[A-Za-z])", r"\1", text)
    text = "".join(" " if unicodedata.category(ch) == "Co" else ch for ch in text)
    text = re.sub(r"[\u2022\u25aa\u25cf\u00b7\u2043\u2219]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _pages_pdfplumber(path: Path) -> list[str]:
    import pdfplumber

    with pdfplumber.open(str(path)) as document:
        return [page.extract_text() or "" for page in document.pages]


def _pages_pdfium(path: Path) -> list[str]:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(path))
    try:
        return [page.get_textpage().get_text_range() for page in document]
    finally:
        document.close()


EXTRACTORS: dict[str, Callable[[Path], list[str]]] = {"pdfplumber": _pages_pdfplumber, "pypdfium2": _pages_pdfium}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def read_reading_order(path: str | Path, extractor: str = "pdfplumber") -> str:
    return normalise_text("\n".join(EXTRACTORS[extractor](Path(path))))


def check_reading_order(path: str | Path, roles: list[dict[str, Any]], *,
                        contacts: Iterable[str] = ()) -> dict[str, Any]:
    """Run two independent extractors and fail when a role's bullets extract out of place.

    ``roles`` is ``[{"employer": str, "dates": str, "bullets": [str]}]`` in reading
    order.  Each role's heading must precede its own bullets, no bullet may land
    inside another role's span, and the two extractors must agree on the token
    order.  This proves reading-order integrity; it is not any vendor's ATS parser.
    """
    failures: list[str] = []
    streams = {name: read_reading_order(path, name) for name in EXTRACTORS}

    def find(stream: str, needle: str, start: int = 0) -> int:
        return stream.find(normalise_text(needle), start)

    for name, stream in streams.items():
        starts: list[tuple[str, int]] = []
        for role in roles:
            at = find(stream, role["employer"])
            if at < 0:
                failures.append(f"[{name}] {role['employer']!r} is missing from extraction")
                continue
            starts.append((role["employer"], at))
            last = at
            for bullet in role.get("bullets", ()):
                bullet_at = find(stream, bullet, at)
                if bullet_at < 0:
                    failures.append(f"[{name}] bullet under {role['employer']!r} did not extract: {bullet[:48]!r}")
                    continue
                if bullet_at < last:
                    failures.append(f"[{name}] bullet under {role['employer']!r} extracts before its heading")
                last = bullet_at
        ordered = sorted(starts, key=lambda pair: pair[1])
        for position, (employer, start) in enumerate(ordered):
            end = ordered[position + 1][1] if position + 1 < len(ordered) else len(stream)
            role = next(r for r in roles if r["employer"] == employer)
            for bullet in role.get("bullets", ()):
                bullet_at = find(stream, bullet)
                if bullet_at >= 0 and not start <= bullet_at < end:
                    failures.append(f"[{name}] bullet of {employer!r} extracts inside another role: {bullet[:48]!r}")
        for contact in contacts:
            if normalise_text(contact) not in stream:
                failures.append(f"[{name}] contact detail did not extract as one string: {contact!r}")
        if not EMAIL_RE.search(stream):
            failures.append(f"[{name}] no email address extracted")

    a, b = streams["pdfplumber"].split(), streams["pypdfium2"].split()
    similarity = difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()
    if similarity < 0.90:
        failures.append(f"extractors disagree on reading order (similarity {similarity:.3f} < 0.90)")
    return {"path": str(path), "ok": not failures, "failures": failures,
            "extractor_similarity": round(similarity, 4)}
