# Job Automation — Task List & Roadmap

Living backlog. Top section = active/agreed; below = the candidate improvements we're discussing.

## 🟢 Done
- [x] **Static, server-less dashboard** — `python -m jobauto dashboard` builds a single
      self-contained `output/dashboard.html` (data + CSS + JS + tailored-doc previews all
      inlined). Opens by double-click, works in the cloud with no server. Approvals build the
      exact CLI commands with a copy button. (`jobauto/static_dashboard.py`.) The FastAPI app
      remains as the "local power user" live option.

## 🔴 Active
- [x] **GitHub Actions discovery workflow built** (`.github/workflows/job-discovery.yml`):
      daily cron + manual dispatch → `check-sources` → `fetch` (ATS APIs + keyless
      aggregators) → `validate-links --reject-dead` → `report` + static `dashboard.html`,
      committed back to the repo. Runs where there IS internet (GH runner), unlike the sandbox.
- [x] Freshness everywhere (`max_age_days: 3`), `validate-links`, posted-date + dead-link
      badges, JSearch/Adzuna/Bundesagentur date params, static dashboard shows unscored jobs.
- [ ] **BLOCKER — the workflow only runs once it's on the DEFAULT branch.** GitHub registers
      `workflow_dispatch`/`schedule` workflows from the default branch only; ours is on
      `claude/job-automation-folder-xXImq`, so `list_workflows` = 0 and dispatch 404s. Needs the
      user's OK to **merge / open a PR to the default branch**. Once there: the cron runs daily,
      AND the first run finally verifies the live ATS tokens + commits real fresh jobs.
- [ ] After it runs: read `check-sources` output, fix/convert any failing Workday tokens to
      `custom`, and (recommended) enable the keyless **Bundesagentur** source for real coverage
      of the German targets (most of them are NOT on Greenhouse/Lever, so ATS-only yield is thin).

## 🟡 Candidate improvements (discuss / prioritise)
**Correctness & data**
- [ ] Verify `companies.yml` ATS tokens on a real OpenClaw run (current tokens are best-guess).
- [ ] Cross-source fuzzy dedup (same job from an aggregator + the company ATS can appear twice).
- [ ] Update `profile.md` with the DLR/D-LIGHT role so scoring context is current.

**Automation & runtime**
- [ ] Live OpenClaw run to validate `fetch` (real ATS + aggregator APIs) end to end.
- [ ] Register the OpenClaw morning cron; confirm host-awake behaviour.
- [ ] Real delivery channel wired (Gmail draft/send or Telegram) instead of just artifacts.
- [ ] Follow-up reminders actually firing (logic exists in `digest`, needs a scheduler).

**Quality of output**
- [ ] Feedback loop: learn from approve/reject to tune scoring + tailoring.
- [ ] PDF filenames as `<Name>_<Company>_<role>.pdf`; auto-date the cover letter.
- [ ] German-language cover-letter variant when a JD requires it.

**Ops / robustness**
- [ ] Tests + a CI check (lint, smoke-run the pipeline on the sample fixtures).
- [ ] Secrets handling doc for the OpenClaw handoff.
- [ ] Scoring rubric calibration; confidence/uncertainty surfaced in the digest.
