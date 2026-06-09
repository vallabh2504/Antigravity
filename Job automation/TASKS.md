# Job Automation — Task List & Roadmap

Living backlog. Top section = active/agreed; below = the candidate improvements we're discussing.

## 🟢 Done
- [x] **Static, server-less dashboard** — `python -m jobauto dashboard` builds a single
      self-contained `output/dashboard.html` (data + CSS + JS + tailored-doc previews all
      inlined). Opens by double-click, works in the cloud with no server. Approvals build the
      exact CLI commands with a copy button. (`jobauto/static_dashboard.py`.) The FastAPI app
      remains as the "local power user" live option.

## 🔴 Active
- [ ] **Cross-check that every aggregator endpoint + companies.yml portal token is reachable**
      so the Python `fetch` actually works. Build `jobauto check-sources` (HTTP HEAD/GET each
      URL, report status). NOTE: this sandbox blocks outbound HTTP, so the checker must run on
      OpenClaw / the user's machine for real results.

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
