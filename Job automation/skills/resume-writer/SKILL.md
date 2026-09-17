---
name: resume-writer
description: >-
  Write the resume half of content.json from plan.json and the candidate's facts: a
  truthful, job-tailored two-page resume as structured JSON for the renderer. Use in the
  writer role of the application workflow.
---

# Resume Writer

1. Read `../house-style/SKILL.md` and `../house-style/references/resume-pattern.md`.
2. Follow `plan.json`: its angle, experience_emphasis, keywords and do_not_claim.
3. Use every relevant role and project from `facts/`. Relevance decides which bullets
   you keep; start date decides the order (reverse chronological).
4. Summary: three sentences, 55-75 words.
5. At most four bullets per role, 14-32 words each, each ending with a period.
   Bullet grammar: action + engineering object + method/tool + purpose + evidence.
6. Paraphrase facts into the job's vocabulary without widening their scope. Every number
   and every proper term must occur in `facts/`; the fact lock rejects anything else.
7. Skills: 3-5 labelled rows, comma-separated items, supported by facts, ordered by
   relevance to this job.
8. The resume must fill its pages (default two A4 pages): the last page substantially
   full, never a short spill.
9. Copy the candidate block (name, preferred_name, email, phone, location, linkedin)
   exactly from `facts/`. The headline is short enough to fit on one line and must
   not introduce terms the facts do not support.

Write only the `candidate` and `resume` parts of `content.json` per
`schema/content_schema.json`. No HTML, no evidence IDs.
