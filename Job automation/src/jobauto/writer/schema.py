"""JSON shapes the agents write.  Copied into every workspace under ``schema/``."""
from __future__ import annotations

from typing import Any

from . import SCHEMA
from .facts import LETTER_TARGET

CONTENT_SCHEMA: dict[str, Any] = {
    "schema": SCHEMA,
    "candidate": {"name": "str", "preferred_name": "str", "headline": "str, fits one line, no dashes",
                  "email": "str", "phone": "str", "location": "str", "linkedin": "str"},
    "resume": {
        "summary": "3 sentences, 55-75 words",
        "experience": [{"title": "str", "org": "str", "location": "str", "start": "MM/YYYY",
                        "end": "MM/YYYY|Present", "bullets": ["14-32 words, ends with a period"]}],
        "projects": [{"name": "str", "org": "str", "start": "MM/YYYY", "end": "MM/YYYY", "bullets": ["..."]}],
        "education": [{"degree": "str", "institution": "str", "location": "str", "start": "MM/YYYY",
                       "end": "MM/YYYY|Present", "details": ["short lines"]}],
        "skills": [{"label": "str", "items": "comma-separated"}],
        "publications": [{"title": "str", "venue": "str", "status": "str", "date": "MM/YYYY"}],
        "languages": "str",
        "section_order": ["summary", "experience", "projects", "education", "skills", "publications", "languages"],
        "page_break_before": "optional: section key or 'experience:<index>' (HTML templates only)",
    },
    "cover_letter": {"recipient_lines": ["str"], "subject": "str", "salutation": "str",
                     "paragraphs": [f"4-5 paragraphs, {LETTER_TARGET[0]}-{LETTER_TARGET[1]} words total"],
                     "closing": "Kind regards,", "signature": "str"},
    "requirement_trace": [{"requirement": "str", "evidence": "where in the facts", "status": "supported|partial|gap"}],
}

REVIEW_SCHEMA: dict[str, Any] = {
    "pass": "bool",
    "content_score": "int 0-100",
    "design_score": "int 0-100",
    "fit_note": "how well the candidate fits the job, independent of execution",
    "findings": [{"severity": "blocker|major|minor", "area": "truth|keywords|coverage|letter|style|design",
                  "where": "document and location", "issue": "what is wrong", "fix": "the exact change"}],
    "reviewed_pdf_sha256": {"resume": "copied from rounds/rN/manifest.json",
                            "cover_letter": "copied from rounds/rN/manifest.json"},
}
