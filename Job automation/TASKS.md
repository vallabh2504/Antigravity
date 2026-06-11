# Job Automation — Task List & Roadmap

Living backlog. Top section = active/agreed; below = the candidate improvements we're discussing.

## 🟢 Done
- [x] **Static, server-less dashboard** — `python -m jobauto dashboard` builds a single
      self-contained `output/dashboard.html` (data + CSS + JS + tailored-doc previews all
      inlined). Opens by double-click, works in the cloud with no server. Approvals build the
      exact CLI commands with a copy button. (`jobauto/static_dashboard.py`.) The FastAPI app
      remains as the "local power user" live option.

## 🟢 Done (verified on the live GitHub-runner network)
- [x] **Discovery runs end-to-end on GitHub Actions** (merged to `main`, ran 3 times). Commits
      `dashboard.html` + `reports/<date>.md` + `source_check.json` back to the repo.
- [x] **Bosch (SmartRecruiters): 42 real fuel-cell jobs**, fresh + link-validated (keyword
      filter `q=fuel cell` works; was 100 generic before).
- [x] **Arbeitnow: 7 jobs.** Workday tokens were all broken (422/404) → converted to `custom`.
- [x] **Bundesagentur HTTP 400 → 200** fixed (`/app/jobs` path + angebotsart/pav + mobile
      User-Agent). Returned 0 for the niche 3-day query — needs query tuning (below).

## 🔴 Active — remaining German-market coverage gap
- [ ] **Bundesagentur returns 200 but 0 jobs** for "Brennstoffzelle Wasserstoff" in a 3-day
      window. Try a broader single keyword ("Brennstoffzelle" OR "Wasserstoff"), widen the
      window, and confirm the response key (`stellenangebote`). This is the source that should
      surface Siemens/BMW/Daimler/MAHLE postings.
- [ ] **26 custom careers pages return 200 but yield nothing to pure Python** (DLR, Airbus,
      cellcentric, Fraunhofer…). They need the agent/browser backend to parse, OR coverage via
      Bundesagentur/JSearch. Decide: agent-parse customs, or add JSearch/Adzuna keys for
      whole-market coverage.

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
