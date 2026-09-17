---
name: cover-letter-writer
description: >-
  Write the cover-letter half of content.json: a one-page, role-specific letter that maps
  the employer's problem to the candidate's strongest evidence. Use in the writer role of
  the application workflow.
---

# Cover-Letter Writer

1. Read `../house-style/SKILL.md` and `../house-style/references/cover-letter-pattern.md`.
2. Extract the role thesis, the top requirements and eligibility constraints from
   `plan.json` and `job/job.md`.
3. Select three or four evidence clusters from `facts/`. Do not repeat the resume
   bullet for bullet.
4. Write 4 or 5 paragraphs, 380-450 words in total. The fact lock allows 340-475; the
   renderer shrinks type slightly to keep one page, so stay inside the target.
5. Name the company. Apply the company-swap test and rewrite any paragraph that would
   still be true for another employer.
6. Be honest about gaps and about `plan.json` operator_questions: do not state a start
   date, supervisor, permit or eligibility the facts do not contain. Write around them.
7. `recipient_lines` and `salutation`: use only names and addresses that appear in the
   job description; otherwise the organisation and "Dear Hiring Team,". Keep umlauts.

Write the `cover_letter` part of `content.json` per `schema/content_schema.json`
(`recipient_lines`, `subject`, `salutation`, `paragraphs`, `closing`, `signature`). The
pipeline sets the date.
