# Job Automation — Task List & Roadmap

Living backlog. Top section = active/agreed; below = the candidate improvements we're discussing.

## 🔴 Active
- [ ] **Dashboard does not work in the cloud/GitHub web session.** The current dashboard is a
      FastAPI server (`dashboard/app.py`) that needs a running localhost process + writable
      `output/jobs.db`. In the ephemeral cloud container there is no persistent server and the
      DB/output is gitignored, so it can't serve. **Proposed fix:** replace (or add) a
      **self-contained static dashboard** — a single `dashboard.html` generated from a
      `jobs.json` export of the DB, with all data inlined and approve/reject handled via
      `mailto:`/copy-command or a tiny localStorage queue. It opens by double-click, commits to
      the repo, and works anywhere with no server. Keep the FastAPI app as the "local power user"
      option. (Decision pending.)

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
