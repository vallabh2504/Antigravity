# Job Automation — Task List & Roadmap

Living backlog. Top section = active/agreed; below = the candidate improvements we're discussing.

## 🟢 Done
- [x] **Static, server-less dashboard** — `python -m jobauto dashboard` builds a single
      self-contained `output/dashboard.html` (data + CSS + JS + tailored-doc previews all
      inlined). Opens by double-click, works in the cloud with no server. Approvals build the
      exact CLI commands with a copy button. (`jobauto/static_dashboard.py`.) The FastAPI app
      remains as the "local power user" live option.

## 🔴 Active
- [x] Built `jobauto check-sources` (pings every token + aggregator endpoint, parses the
      response to confirm real jobs return). Sandbox blocks egress, so RUN IT ON OPENCLAW /
      YOUR MACHINE for real results.
- [x] Spot-verified the structured-API tokens via web search: **Bosch SmartRecruiters
      `BoschGroup` = correct ✓**; **ZeroAvia (was greenhouse) and Ballard (was lever) were
      WRONG → fixed to custom portals.**
- [ ] **Still UNVERIFIED (need the live `check-sources` run):** the 9 Workday tokens (Airbus,
      Alstom, Siemens Mobility, Daimler Truck, BMW, Volvo, Cummins, Rolls-Royce, Honeywell) and
      the 1 Greenhouse token (Intelligent Energy). Workday tenant/site paths can't be confirmed
      from search snippets; the live checker will validate or flag each. Likely several are wrong
      and should drop to `custom` (agent-fetched) if their CXS endpoint 404s.
- [ ] Aggregator keys: Adzuna needs a free `app_id`/`app_key` in `secrets.yml`; Arbeitnow,
      Bundesagentur (public key), EURAXESS need no key. `check-sources` will confirm once online.

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
