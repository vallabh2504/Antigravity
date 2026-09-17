---
name: house-style
description: >-
  Write and review resumes, cover letters and application plans in the evidence-led house
  style. Use for every application document in this project, especially when selecting
  claims, constructing technical bullets, or checking whether prose sounds generic,
  inflated or machine-written.
---

# House Style

Write as a calm engineer or researcher. Prove capability with technical objects, methods,
validation, scale and measured outcomes. Never replace evidence with self-praise.

## Where the truth lives

The candidate's facts are the files in `facts/` of the application workspace
(`master_resume.yml`, `profile.md`, and `writer_answers.md` once the candidate has
answered open questions). Nothing else is a source of truth about the candidate: not
the job description, not the examples, not your general knowledge.

A mechanical **fact lock** checks the documents: every number and every proper term
(tool, organisation, acronym, product) in the resume must occur in `facts/`. The cover
letter may additionally name terms from the job description, because a letter speaks
about the employer's work.

## Workflow

1. The planner maps job requirements to verbatim fact quotes (`plan.json`).
2. The writer drafts from the plan. Read [resume-pattern.md](references/resume-pattern.md)
   for resume work and [cover-letter-pattern.md](references/cover-letter-pattern.md) for
   letter work.
3. A reviewer who did not write the documents checks the rendered PDFs against
   [quality-gates.md](references/quality-gates.md).

## Voice

- Technical, evidence-led, direct and credible.
- Prefer demonstrated competence over adjectives about the candidate.
- Past tense for completed work; present tense only for ongoing work.
- Keep terminology and capitalisation consistent.
- Use ASCII hyphens only inside compounds. No em dashes or en dashes as punctuation.
- Keep umlauts and accents in proper nouns exactly as the source spells them
  ("für", not "fuer").
- No generic enthusiasm, company admiration, theatrical metaphors or keyword dumps.

## Non-negotiable truth rules

- Never invent a title, date, employer, tool, result, metric, scope, affiliation,
  publication status, start date, supervisor, work permit or company fact.
- Never turn planned work into completed work.
- Never broaden a narrow fact into a system-level claim.
- A job-description keyword may appear in the resume only where a fact supports it.
  Paraphrasing a fact into the job's vocabulary is good; importing the job's vocabulary
  as experience the facts do not show is fabrication.
- If evidence is incomplete, omit the claim or state the limitation.
- Any unsupported claim fails the document regardless of visual quality.

## Banned phrasing

Do not write: `highly motivated`, `seeking a position`, `perfect fit`, `ideal candidate`,
`uniquely suited`, `passionate about`, `keen interest`, `I am confident that`,
`leverage my skill set`, `synergy`, `cutting-edge solutions`, `profound interest`,
`unique blend`, or `regardless of the outcome`.

## Output principle

Write structured JSON, never HTML. The renderer owns geometry, typography, pagination
and PDF metadata; the chosen template decides the look.
