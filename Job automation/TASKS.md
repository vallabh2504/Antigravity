# Job Automation — Task List & Roadmap

Living backlog. Top section = active/agreed; below = the candidate improvements we're discussing.

## 🟢 Done
- [x] **JobSpy discovery backbone (no API key)** — replaced paid JSearch/RapidAPI with
      open-source JobSpy (LinkedIn/Indeed/Google/Glassdoor). One run pulled 278 raw → 88
      relevant → 58 fresh fuel-cell jobs in the last 1-2 days. (`sources/jobspy_source.py`.)
- [x] **Link validation that actually runs** — validates `discovered` jobs, distinguishes
      genuinely-gone (404/410, auto-rejected) from bot-blocked (403/999, kept as "unverified").
- [x] **Redesigned dashboard UI** — dark, modern "Fuel-Cell Job Radar": score rings, fit
      reasons, sector/freshness/link badges, tailored-doc ribbons, JD/Résumé/Cover viewer,
      quick filters (Strong / Tailored / Thesis-Werkstudent). (`jobauto/static_dashboard.py`.)
- [x] **Real LLM relevance scoring (by the agent, not a script)** — all 58 jobs scored 0-100
      with sector, work-type, German level and specific fit reasons. Gems surface (BMW
      Brennstoffzelle 90, ZSW AEM thesis 82, REVERION 80); car-sales/tax/AI-founder noise sinks.
- [x] **Curated tailored applications for the top 3** — résumé + cover letter for BMW (#29),
      ZSW AEM Stuttgart (#23), REVERION (#40), each pulling DIFFERENT real experience, in
      Vallabh's voice via the house-style/resume/cover skills, verified ZERO em-dashes.
- [x] **Cron no longer clobbers the curated dashboard** — daily run writes raw discovery to
      `auto_latest.html` + a `latest_jobs.json` snapshot (`dump-jobs`); the agent re-enriches
      `dashboard.html`.

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
