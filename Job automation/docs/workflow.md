# Application workflow

This is the contract between the three agent roles and the code gates. The prompt
(`PROMPT.md`) and the role files (`workspace/roles/*.md`) are generated from
`src/jobauto/writer/kit.py` and `src/jobauto/writer/prompts.py`.

## Folders

```
Applications/<company-role>/
  PROMPT.md          the prompt you paste into an agent
  job.json           the posting as stored in the database
  status.json        stage, round, attempts, fit, questions, reviews, history
  plan.json          copy of the accepted plan
  questions.md       what only you can answer
  templates/         every rendered template of the latest round
  reviews/round_N.json
  final/             upload-named PDFs once the result is docs_ready or hold
  workspace/         where the agents work (see below)

workspace/
  roles/             planner.md, writer.md, reviewer.md
  job/job.md         the job description (edit it if the scraped text was truncated)
  facts/             copies of your master_resume.yml, profile.md, writer_answers.md
  skills/            house-style, jd-evidence-planner, resume-writer, cover-letter-writer, application-reviewer
  schema/            plan, content and review JSON shapes
  examples/          your writer_examples, or the fictional sample
  plan.json, content.json, review.json   written by the roles
  rounds/rN/         resume.pdf, cover_letter.pdf, previews/, render_report.json, manifest.json
  round.txt          the current round folder
  FEEDBACK.md        what the next role has to fix
```

`facts/`, `roles/`, `skills/`, `schema/` and `examples/` are rewritten on every
`prepare`, so an agent cannot change its own rules or facts.

## Gates

| Gate | Checks | Results |
|---|---|---|
| `check-plan` | `plan.json` shape; every job quote verbatim in `job/job.md`; every fact quote verbatim in `facts/` | `plan_ok`, `fix_plan`, `needs_operator` after `max_fix_attempts` |
| `render` | the plan still passes; `content.json` changed since the last review; fact lock; renders every template; machine QA | `rendered`, `fix_content`, `needs_operator` |
| `finalize` | round PDFs unchanged; `review.json` exists; scores >= `min_scores`; no blocker or major finding; `pass: true`; review bound to the PDF hashes | `docs_ready`, `hold`, `revise`, `needs_operator` after `max_review_rounds` |

Every gate writes `status.json`, prints `RESULT:` and `NEXT:`, and on failure writes
`FEEDBACK.md` for the role that has to act.

## Hold

A passing application still ends in `hold` (job stays in `docs_review`) when
`hold_on_weak_fit` is true and the plan's fit verdict is `weak`, or an `eligibility`
requirement is a `gap`. The documents are in `final/`; the decision is yours.

## Job states

`discovered -> scored -> approved -> docs_review -> docs_ready -> applied -> ...`,
plus `rejected`. `render` moves an approved job to `docs_review`; `finalize` moves it
to `docs_ready` on a pass without hold. `applied` is always set by you.
