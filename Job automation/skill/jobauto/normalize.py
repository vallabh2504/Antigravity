"""Stage 2: normalize raw postings → Job, dedupe, store."""
from __future__ import annotations

import html
import re
from typing import Iterable

from .db import DB
from .models import Job, RawPosting

_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<\s*br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</\s*(p|li|div|h\d)\s*>", "\n", text, flags=re.I)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def normalize(raw: RawPosting) -> RawPosting:
    raw.title = (raw.title or "").strip()
    raw.company = (raw.company or "").strip()
    raw.location = (raw.location or "").strip()
    raw.jd_text = strip_html(raw.jd_text)
    return raw


def ingest(db: DB, raws: Iterable[RawPosting]) -> dict[str, int]:
    """Normalize + dedupe + store. Returns {'new': n, 'dup': n}."""
    new = dup = 0
    for r in raws:
        job = Job.from_raw(normalize(r))
        if db.upsert(job):
            new += 1
        else:
            dup += 1
    return {"new": new, "dup": dup}
