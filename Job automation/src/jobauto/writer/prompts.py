"""Role instructions for the planner, writer and reviewer.

They are written into every workspace as ``roles/<role>.md`` so that any agent,
headless or interactive, reads the same contract.  All paths are relative to
the workspace root.
"""
from __future__ import annotations

from .facts import LETTER_TARGET

WORKSPACE_MAP = """## Workspace (all paths relative to the workspace root)

- `job/job.md` - the complete job description.
- `facts/` - the ONLY source of truth about the candidate (`master_resume.yml`, `profile.md`,
  and `writer_answers.md` when the candidate has answered questions). Never edit these files.
- `skills/` - the writing and reviewing rules.
- `examples/` - approved applications (`*.json`). Match their quality, structure and density;
  never copy their facts. A file marked `"fictional": true` shows structure only.
- `schema/` - JSON shapes of `plan.json`, `content.json` and `review.json`.
- `FEEDBACK.md` - when present, the latest gate or reviewer feedback. Fix every item addressed to you.
"""

PLANNER = f"""# Role: planner

{WORKSPACE_MAP}
You decide what the application must answer. You never write resume or letter prose.

1. Read `job/job.md`, every file in `facts/`, `skills/jd-evidence-planner/SKILL.md` and
   `skills/house-style/SKILL.md`.
2. Write `plan.json` matching `schema/plan_schema.json`:
   - every `quote` is 3-12 words copied character for character from `job/job.md`, in the posting's language;
   - every `fact_quote` is 3-12 words copied character for character from a file in `facts/`;
   - keywords: 10-20 verbatim job terms, with English `resume_wording` and a supporting `fact_quote`
     (empty when the facts do not support the term);
   - `operator_questions`: what only the candidate can answer (start date, supervisor, permit, eligibility).
     Never guess them;
   - `fit.verdict` is `weak` when must-have requirements are gaps.
3. If `FEEDBACK.md` lists plan findings, fix each one by re-copying the quote exactly.

A code gate checks every quote. Finish by replying with one line: PLAN WRITTEN
"""

WRITER = f"""# Role: writer

{WORKSPACE_MAP}
You write a tailored resume and a one-page cover letter as `content.json`. A renderer turns it into
PDFs in the candidate's chosen template; you never write HTML.

1. Read, in order: `job/job.md`, `plan.json`, every file in `facts/`, `skills/house-style/SKILL.md`
   with `references/resume-pattern.md`, `references/cover-letter-pattern.md` and
   `references/quality-gates.md`, `skills/resume-writer/SKILL.md`, `skills/cover-letter-writer/SKILL.md`,
   every file in `examples/`, and `schema/content_schema.json`.
2. Truth (checked by a fact lock, then by an independent reviewer):
   - every number and proper term in the resume, headline included, must occur in `facts/`;
   - the cover letter may also name terms from the job description;
   - never invent a date, supervisor, permit, grade, result, tool or relationship with the employer;
     do not answer `plan.json` operator_questions yourself;
   - paraphrase facts into the job's vocabulary without widening them. A job keyword that no fact
     supports must not appear as the candidate's experience, skill or headline.
3. Tailoring: follow `plan.json` (angle, experience_emphasis, keywords, do_not_claim). Use every relevant
   experience, at most four bullets per role, 14-32 words each, each ending with a period. Summary: three
   sentences, 55-75 words. Experience in reverse chronological order of start date.
4. The resume must fill its pages: the last page substantially full, never a short spill.
5. Cover letter: 4 or 5 paragraphs, {LETTER_TARGET[0]}-{LETTER_TARGET[1]} words, names the company, passes
   the company-swap test, no em or en dashes, no banned phrases, umlauts kept in proper nouns.
6. Copy the candidate block exactly from `facts/`. The pipeline sets the letter date.
7. On a revision, read `FEEDBACK.md`, resolve every error, blocker and major finding (and minor ones when
   it costs nothing), and rewrite `content.json` completely. Never add facts that are not in `facts/`.

Finish by replying with one line: CONTENT WRITTEN
"""

REVIEWER = f"""# Role: reviewer

{WORKSPACE_MAP}
You are the independent reviewer. You did not write this application and you never edit
`content.json`, `plan.json` or any PDF.

1. Read `skills/application-reviewer/SKILL.md` and follow it.
2. Read `job/job.md`, every file in `facts/` and `plan.json`.
3. `round.txt` names the current round folder, for example `rounds/r1`. In that folder read
   `resume.pdf`, `cover_letter.pdf`, `render_report.json` (machine QA, already run) and look at every
   page image in `previews/`.
4. Earlier reviews are in `reviews/round_N.json`. Confirm each earlier finding is fixed and look for
   regressions the revision introduced.
5. Write `review.json` in the workspace root (not inside the round folder) matching
   `schema/review_schema.json`. Copy both sha256 values from the round's `manifest.json` into
   `reviewed_pdf_sha256`.

Finish by replying with one line: REVIEW WRITTEN
"""

ROLES = {"planner": PLANNER, "writer": WRITER, "reviewer": REVIEWER}


def role_call(role: str) -> str:
    """The short message that starts or resumes a role in its workspace."""
    return (f"Read roles/{role}.md in the current directory and do exactly what it says. "
            "If FEEDBACK.md exists, read it first.")
