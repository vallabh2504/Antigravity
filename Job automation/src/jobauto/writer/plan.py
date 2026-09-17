"""Mechanical checks on the planner agent's requirement-to-evidence plan.

The planner is an agent because reading a job description is judgement: it
has to tell a real requirement from recruiting filler and see that a fuel-cell
test bench is laboratory experience.  What an agent cannot be trusted with is
provenance, so every claim in the plan must carry a verbatim quote: the
requirement from the job description, the evidence from the operator's facts.
A quote that is not found is a finding the planner has to fix.
"""
from __future__ import annotations

import re
from typing import Any

from .facts import FactCorpus, Finding, _fold, clean_job_text

KINDS = {"must", "nice", "responsibility", "eligibility"}
STATUSES = {"supported", "partial", "gap"}
FITS = {"strong", "partial", "weak"}

PLAN_SCHEMA: dict[str, Any] = {
    "fit": {"verdict": "strong|partial|weak", "reason": "one or two sentences"},
    "requirements": [{
        "kind": "must|nice|responsibility|eligibility",
        "quote": "verbatim phrase copied from the job description",
        "status": "supported|partial|gap",
        "evidence": [{"fact_quote": "verbatim phrase copied from the facts", "why": "how it answers the requirement"}],
    }],
    "keywords": [{"term": "verbatim job-description term", "resume_wording": "how the resume should say it",
                  "fact_quote": "verbatim phrase from the facts that supports it, or empty when unsupported"}],
    "angle": "the application's thesis in two or three sentences",
    "experience_emphasis": [{"role": "title at organisation", "lead_with": "what this role should foreground"}],
    "operator_questions": ["a question only the operator can answer, e.g. earliest start date"],
    "do_not_claim": ["job requirements the facts do not support and the documents must not imply"],
}


def _norm(text: str) -> str:
    text = _fold(clean_job_text(text))
    text = re.sub(r"[*_#`>|]", " ", text)
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip()


def _found(quote: str, haystack: str) -> bool:
    needle = _norm(quote).strip(" .,;:")
    return bool(needle) and needle in haystack


def validate_plan(plan: Any, job: dict[str, Any], corpus: FactCorpus) -> list[Finding]:
    """Return every structural and provenance finding for a planner plan."""
    out: list[Finding] = []
    if not isinstance(plan, dict):
        return [Finding("error", "plan", "plan must be a JSON object")]
    jd = _norm(job.get("jd_text", ""))
    facts = re.sub(r"[*_#`>|]", " ", corpus.text)
    facts = re.sub(r"\s+", " ", facts.replace("’", "'"))

    fit = plan.get("fit")
    if not isinstance(fit, dict) or fit.get("verdict") not in FITS or not str(fit.get("reason", "")).strip():
        out.append(Finding("error", "fit", f"fit needs verdict in {sorted(FITS)} and a reason"))
    if not str(plan.get("angle", "")).strip():
        out.append(Finding("error", "angle", "angle is empty"))

    requirements = plan.get("requirements")
    if not isinstance(requirements, list) or len(requirements) < 3:
        out.append(Finding("error", "requirements", "list at least three requirements from the job description"))
        requirements = requirements if isinstance(requirements, list) else []
    for i, req in enumerate(requirements):
        where = f"requirements[{i}]"
        if not isinstance(req, dict):
            out.append(Finding("error", where, "must be an object"))
            continue
        if req.get("kind") not in KINDS:
            out.append(Finding("error", where, f"kind must be one of {sorted(KINDS)}"))
        if req.get("status") not in STATUSES:
            out.append(Finding("error", where, f"status must be one of {sorted(STATUSES)}"))
        if not _found(str(req.get("quote", "")), jd):
            out.append(Finding("error", where, f"quote not found verbatim in the job description: {req.get('quote')!r}"))
        evidence = req.get("evidence") or []
        if req.get("status") in ("supported", "partial") and not evidence:
            out.append(Finding("error", where, "a supported or partial requirement needs evidence"))
        for j, ev in enumerate(evidence if isinstance(evidence, list) else []):
            quote = ev.get("fact_quote", "") if isinstance(ev, dict) else ""
            if not _found(str(quote), facts):
                out.append(Finding("error", f"{where}.evidence[{j}]",
                                   f"fact_quote not found verbatim in the facts: {quote!r}"))

    for i, kw in enumerate(plan.get("keywords") or []):
        where = f"keywords[{i}]"
        if not isinstance(kw, dict):
            out.append(Finding("error", where, "must be an object"))
            continue
        if not _found(str(kw.get("term", "")), jd):
            out.append(Finding("error", where, f"term not found in the job description: {kw.get('term')!r}"))
        quote = str(kw.get("fact_quote", "") or "")
        if quote and not _found(quote, facts):
            out.append(Finding("error", where, f"fact_quote not found verbatim in the facts: {quote!r}"))

    for key in ("operator_questions", "do_not_claim", "experience_emphasis"):
        if not isinstance(plan.get(key, []), list):
            out.append(Finding("error", key, "must be a list"))
    return out
