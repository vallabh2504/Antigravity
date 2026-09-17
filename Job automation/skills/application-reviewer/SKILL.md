---
name: application-reviewer
description: >-
  Independently review a rendered resume and cover letter (the PDFs and their page
  images) for truth, tailoring, style and visual quality, and write review.json bound to
  the PDFs' SHA-256. Use in the reviewer role; the reviewer never edits the documents.
---

# Application Reviewer

You did not write these documents, and you never edit them. You judge the PDFs a
recruiter will receive, not the JSON behind them.

## Inputs

- `job/job.md`, every file in `facts/`, `plan.json`.
- `rounds/rN/resume.pdf`, `rounds/rN/cover_letter.pdf` and every image in
  `rounds/rN/previews/`.
- `rounds/rN/render_report.json` - machine QA already run (page count, A4, text
  extraction, reading order). Do not re-run it.
- `rounds/rN/manifest.json` - the SHA-256 of the PDFs in this round.
- `../house-style/SKILL.md` and its `references/`.

## Check

1. **Truth.** Every claim traceable to `facts/` in meaning. Look hardest at the
   headline, summary and skills: a job-description phrase presented as the candidate's
   experience without a supporting fact is a blocker. So are widened scope, invented
   numbers and planned work shown as done.
2. **Keyword fit.** The job's important terms appear, truthfully, where facts support them.
3. **Coverage.** All relevant experience used; nothing important from `plan.json` missing.
4. **Letter.** Specific to this employer and role; answers its requirements; honest about
   gaps and open questions; passes the company-swap test.
5. **Style.** House style, no banned phrases, no dashes as punctuation, consistent
   terms, umlauts kept, ambiguous abbreviations spelled out once.
6. **Design** (from the page images). Resume fills its pages; letter is one page; no
   orphan headings, one-word wrapped lines, awkward breaks, clipping or large empty areas.

## Scoring

`content_score` and `design_score` (0-100) grade execution given these facts. A missing
qualification the documents handle honestly is a fit problem: describe it in `fit_note`
and do not deduct for it.

Severity: **blocker** = untrue or unsupported claim, wrong contact detail, broken layout;
**major** = would noticeably weaken the application; **minor** = polish. Every finding
names where it is and the exact fix.

`pass` is true only when both scores are at least 90 and there is no blocker or major
finding. Be strict: a 90 means a hiring engineer would find nothing to fix that matters.

## Output

Write `review.json` in the workspace root per `schema/review_schema.json`, copying the
SHA-256 values from `rounds/rN/manifest.json` into `reviewed_pdf_sha256`. In a later
round, confirm each earlier finding is fixed and look for regressions.
