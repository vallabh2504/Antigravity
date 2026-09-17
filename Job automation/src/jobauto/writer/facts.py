"""Fact corpus and the fact lock for application content.

The writer may paraphrase freely so the job's vocabulary appears; the lock
keeps the facts fixed:

* every number in the prose must occur in the candidate's fact sources;
* every proper term (acronym, tool name, capitalised name not opening a
  sentence) must occur in the fact sources.  Cover-letter prose may also use
  terms from the job description, because a letter names the employer's
  problem.  A resume may not: a job-description tool that is not in the facts
  is exactly the fabrication this lock exists to stop.

The lock cannot judge whether a paraphrase changed a claim's meaning.  That is
the reviewer's job; the lock removes the mechanical failure modes so the
reviewer can spend its attention there.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from .. import config
from ..pdf import BANNED_PHRASES

#: Capitalised words that are ordinary English at any position, or that every
#: application uses.  They are not claims and need no fact source.
COMMON_TERMS = {
    "i", "a", "an", "the", "my", "in", "on", "at", "for", "to", "of", "and", "with", "as", "by",
    "dear", "kind", "regards", "sincerely", "yours", "thank", "best", "mr", "ms", "dr", "ing",
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
    "sept", "oct", "nov", "dec", "present", "today", "english", "german", "germany",
    "native", "fluent", "master", "masters", "thesis", "application", "team", "hiring",
    "manager", "university", "student", "engineering", "engineer", "profile", "experience",
    "education", "skills", "projects", "publications", "languages", "summary", "subject",
    "re", "hello", "this", "that", "these", "those", "there", "here", "during", "after", "before",
    "while", "when", "where", "which", "what", "why", "how", "both", "each", "every", "over",
    "across", "from", "into", "through", "together", "working", "building", "at", "it", "its",
    "since", "because", "so", "if", "then", "also", "one", "two", "three", "four", "five", "six",
    "seven", "eight", "nine", "ten", "m.sc", "b.sc", "b.tech", "gpa", "cgpa",
}

#: Word budgets: the writer aims at the target, the fact lock enforces the limits.
LETTER_TARGET = (380, 450)
LETTER_WORDS = (340, 475)
SUMMARY_WORDS = (45, 90)

_NUMBER_RE = re.compile(r"(?<![A-Za-z])\d+(?:[.,]\d+)?")
_TERM_RE = re.compile(r"[0-9]*[A-Za-z][A-Za-z0-9+/&.\-]*[A-Za-z0-9+]|[0-9]*[A-Za-z]")
_DASHES = {"‒", "–", "—", "―", "−"}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKC", str(text))
    return text.replace("–", "-").replace("—", "-").lower()


@dataclass
class FactCorpus:
    """Searchable text of the operator's fact sources."""

    text: str
    numbers: set[str]
    sources: list[str] = field(default_factory=list)

    def has_term(self, term: str) -> bool:
        needle = _fold(term).strip(".")
        if not needle:
            return True
        return re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", self.text) is not None

    def has_number(self, number: str) -> bool:
        return _norm_number(number) in self.numbers


def _norm_number(value: str) -> str:
    value = value.replace(",", ".")
    if "." in value:
        value = value.rstrip("0").rstrip(".")
    return value.lstrip("0") or "0"


def _flatten(node: Any) -> Iterable[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _flatten(value)
    elif isinstance(node, list):
        for value in node:
            yield from _flatten(value)
    elif node is not None:
        yield str(node)


def load_fact_corpus(profile_dir: str | Path | None = None, extra_texts: Iterable[str] = ()) -> FactCorpus:
    """Build the corpus from ``master_resume.yml``, ``profile.md`` and ``writer_answers.md``."""
    base = Path(profile_dir) if profile_dir else config.profile_dir()
    parts: list[str] = []
    sources: list[str] = []
    master = base / "master_resume.yml"
    if master.is_file():
        data = yaml.safe_load(master.read_text(encoding="utf-8")) or {}
        parts.extend(_flatten(data))
        sources.append(str(master))
    narrative = base / "profile.md"
    if narrative.is_file():
        parts.append(narrative.read_text(encoding="utf-8"))
        sources.append(str(narrative))
    # The operator's answers to the planner's questions (start date, supervisor, permit).
    answers = base / "writer_answers.md"
    if answers.is_file():
        parts.append(answers.read_text(encoding="utf-8"))
        sources.append(str(answers))
    parts.extend(extra_texts)
    text = _fold("\n".join(parts))
    # Unit-glued numbers such as "129kW" or "455-cell" still count.
    numbers = {_norm_number(n) for n in _NUMBER_RE.findall(text)}
    return FactCorpus(text=text, numbers=numbers, sources=sources)


def clean_job_text(text: str) -> str:
    """Remove scraper artefacts from a job description without changing words."""
    text = str(text or "")
    try:
        repaired = text.encode("cp1252").decode("utf-8")
        text = repaired
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass
    text = text.replace("�", " ").replace("\\-", "-").replace("\\&", "&").replace("\\*", "*")
    text = text.replace("\\[", "[").replace("\\]", "]")
    return re.sub(r"[ \t]+", " ", text)


# ---------------------------------------------------------------------------
# content traversal
# ---------------------------------------------------------------------------

def resume_prose(content: dict[str, Any]) -> list[tuple[str, str]]:
    """Every free-text field of the resume, as ``(location, text)``."""
    resume = content.get("resume", {})
    rows: list[tuple[str, str]] = []
    if content.get("candidate", {}).get("headline"):
        rows.append(("candidate.headline", content["candidate"]["headline"]))
    if resume.get("summary"):
        rows.append(("resume.summary", resume["summary"]))
    for group in ("experience", "projects"):
        for i, entry in enumerate(resume.get(group, [])):
            for key in ("title", "org", "name"):
                if entry.get(key):
                    rows.append((f"resume.{group}[{i}].{key}", entry[key]))
            for j, bullet in enumerate(entry.get("bullets", [])):
                rows.append((f"resume.{group}[{i}].bullets[{j}]", bullet))
    for i, entry in enumerate(resume.get("education", [])):
        for j, detail in enumerate(entry.get("details", [])):
            rows.append((f"resume.education[{i}].details[{j}]", detail))
    for i, row in enumerate(resume.get("skills", [])):
        # Category labels are headings, not claims; only the items are locked.
        rows.append((f"resume.skills[{i}]", str(row.get("items", ""))))
    for i, pub in enumerate(resume.get("publications", [])):
        rows.append((f"resume.publications[{i}]", f"{pub.get('title', '')} {pub.get('venue', '')}"))
    return rows


def letter_prose(content: dict[str, Any]) -> list[tuple[str, str]]:
    letter = content.get("cover_letter", {})
    rows = [(f"cover_letter.paragraphs[{i}]", p) for i, p in enumerate(letter.get("paragraphs", []))]
    for key in ("subject", "salutation"):
        if letter.get(key):
            rows.append((f"cover_letter.{key}", letter[key]))
    for i, line in enumerate(letter.get("recipient_lines") or []):
        rows.append((f"cover_letter.recipient_lines[{i}]", str(line)))
    return rows


def words(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'/+.\-]*", str(text)))


def _proper_terms(text: str) -> list[str]:
    """Acronyms, tool-like tokens, and capitalised words not opening a sentence."""
    found: list[str] = []
    for sentence in re.split(r"(?<=[.!?:;])\s+|\n+", str(text)):
        tokens = list(_TERM_RE.finditer(sentence))
        for index, match in enumerate(tokens):
            token = match.group(0).strip(".-/")
            if not token:
                continue
            lower = token.lower()
            if lower in COMMON_TERMS:
                continue
            upper_count = sum(1 for ch in token if ch.isupper())
            tool_like = upper_count >= 2 or any(ch.isdigit() for ch in token) or "+" in token
            capitalised = token[0].isupper() and index > 0
            if tool_like or capitalised:
                found.append(token)
    return found


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    level: str  # "error" | "warning"
    where: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"level": self.level, "where": self.where, "message": self.message}


def _style(where: str, text: str, out: list[Finding]) -> None:
    if any(ch in text for ch in _DASHES):
        out.append(Finding("error", where, "contains an em/en dash; rewrite the sentence"))
    if " - " in text:
        out.append(Finding("warning", where, "spaced hyphen used as a dash"))
    if "�" in text:
        out.append(Finding("error", where, "contains a replacement character"))
    lowered = text.lower()
    for phrase in BANNED_PHRASES:
        if phrase in lowered:
            out.append(Finding("error", where, f"banned phrase: {phrase!r}"))


def _lock(where: str, text: str, corpus: FactCorpus, allowed: FactCorpus | None,
          out: list[Finding]) -> None:
    for number in _NUMBER_RE.findall(text):
        if corpus.has_number(number) or (allowed and allowed.has_number(number)):
            continue
        out.append(Finding("error", where, f"number {number!r} is not in the fact sources"))
    seen: set[str] = set()
    for term in _proper_terms(text):
        key = term.lower()
        if key in seen:
            continue
        seen.add(key)
        if corpus.has_term(term) or (allowed and allowed.has_term(term)):
            continue
        # Compound tokens pass when each part is a known term ("MATLAB/Simulink").
        parts = [p for p in re.split(r"[/&+\-]", term) if p]
        if len(parts) > 1 and all(corpus.has_term(p) or p.lower() in COMMON_TERMS
                                  or (allowed and allowed.has_term(p)) for p in parts):
            continue
        out.append(Finding("error", where, f"term {term!r} is not in the fact sources"))


def _date_key(value: str) -> tuple[int, int]:
    value = str(value or "").strip().lower()
    if value in {"present", "today", "now", ""}:
        return (9999, 12)
    match = re.search(r"(\d{1,2})/(\d{4})", value)
    if match:
        return (int(match.group(2)), int(match.group(1)))
    match = re.search(r"(\d{4})", value)
    return (int(match.group(1)), 1) if match else (0, 0)


def validate_writer_content(content: dict[str, Any], job: dict[str, Any] | None = None,
                            corpus: FactCorpus | None = None) -> list[Finding]:
    """Return every fact-lock, style and budget finding for writer v2 content."""
    corpus = corpus or load_fact_corpus()
    job_corpus = None
    if job:
        job_text = clean_job_text(" ".join(str(job.get(k, "")) for k in ("company", "title", "location", "jd_text")))
        job_corpus = FactCorpus(text=_fold(job_text), numbers={_norm_number(n) for n in _NUMBER_RE.findall(job_text)})
    out: list[Finding] = []
    for key in ("candidate", "resume", "cover_letter"):
        if not isinstance(content.get(key), dict):
            out.append(Finding("error", key, "missing section"))
    if any(f.level == "error" for f in out):
        return out

    resume = content["resume"]
    for where, text in resume_prose(content):
        _style(where, text, out)
        _lock(where, text, corpus, None, out)
    for where, text in letter_prose(content):
        _style(where, text, out)
        _lock(where, text, corpus, job_corpus, out)

    summary_words = words(resume.get("summary", ""))
    if not SUMMARY_WORDS[0] <= summary_words <= SUMMARY_WORDS[1]:
        out.append(Finding("error", "resume.summary",
                           f"{summary_words} words; target 55-75, hard limits {SUMMARY_WORDS[0]}-{SUMMARY_WORDS[1]}"))
    for group in ("experience", "projects"):
        for i, entry in enumerate(resume.get(group, [])):
            if not entry.get("bullets"):
                out.append(Finding("error", f"resume.{group}[{i}]", "no bullets"))
            for j, bullet in enumerate(entry.get("bullets", [])):
                n = words(bullet)
                if n < 10 or n > 38:
                    out.append(Finding("warning", f"resume.{group}[{i}].bullets[{j}]", f"{n} words; target 14-32"))
                if not bullet.rstrip().endswith("."):
                    out.append(Finding("error", f"resume.{group}[{i}].bullets[{j}]", "bullet must end with a period"))
    # Reverse chronology by start date: a long-running student-team role that
    # is still open does not outrank a completed industry internship begun later.
    starts = [_date_key(e.get("start", "")) for e in resume.get("experience", [])]
    for i in range(1, len(starts)):
        if starts[i] > starts[i - 1]:
            out.append(Finding("error", f"resume.experience[{i}]", "experience is not in reverse chronological order"))

    letter = content["cover_letter"]
    paragraphs = letter.get("paragraphs", [])
    letter_words = sum(words(p) for p in paragraphs)
    if not 4 <= len(paragraphs) <= 5:
        out.append(Finding("error", "cover_letter.paragraphs", f"{len(paragraphs)} paragraphs; need 4-5"))
    if not LETTER_WORDS[0] <= letter_words <= LETTER_WORDS[1]:
        out.append(Finding("error", "cover_letter.paragraphs",
                           f"{letter_words} words; target {LETTER_TARGET[0]}-{LETTER_TARGET[1]}, "
                           f"hard limits {LETTER_WORDS[0]}-{LETTER_WORDS[1]}"))
    company = (job or {}).get("company") or content.get("job", {}).get("company", "")
    if company and not any(company.split()[0].lower() in p.lower() for p in paragraphs):
        out.append(Finding("error", "cover_letter.paragraphs", f"letter never names {company!r}"))
    return out


def errors(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f.level == "error"]
