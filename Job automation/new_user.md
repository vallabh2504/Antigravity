# New User Setup — Retargeting Job Automation to Your Profile

This system was built and tuned for **Vallabh Pataneni's** fuel-cell/hydrogen job & PhD
search (aviation > rail > heavy vehicles, Stuttgart-first). Almost every file has his real
name, résumé content, target companies, and search keywords baked into it — as *data*, not
as hardcoded logic. If you're reusing this repo, nothing needs to be rewritten in Python;
you need to **replace the personalization layer** with your own. This doc is the checklist.

## Is it working? (current state, for context)

Yes, the discovery half runs unattended:
- `.github/workflows/job-discovery.yml` fires daily at 06:00 UTC on GitHub's own runners
  (real internet access, unlike a Claude Code sandbox), hits ~66 sources
  (`skill/companies.yml` portals + Adzuna/Arbeitnow/Bundesagentur/EURAXESS), validates
  links, and commits `reports/YYYY-MM-DD.md` + `dashboard/auto_latest.html` back to the repo.
  ~40/66 sources currently resolve; the rest are dead/unverified ATS tokens (expected —
  `companies.yml` says so).
- Scoring shown in the daily report is just the cheap rules prefilter (keyword/location).
  **Real 0–100 LLM scoring, tailoring, and application writing are not automated** — they
  happen when a human runs an agent session (Claude Code or OpenClaw) and asks it to score/
  tailor/apply. The 3 folders under `applications/` (ElringKlinger, FZ Jülich, REVERION) are
  examples of that manual step already done for Vallabh.
- Pre-fill (stage 6, browser form-filling) and auto-submit are **not** wired up in this repo
  yet — `SKILL.md` describes the intended flow but it's agent-driven, on-demand only.

So: the plumbing works end-to-end, but "fully autonomous" is aspirational. What runs on a
schedule without you is discovery + filtering; everything from scoring onward still needs an
agent session or a human.

---

## What "belongs to Vallabh" and must change

### 1. Your profile — `profile.md`
Rewrite completely: field/target roles, seniority, location preference, language level,
education, work experience, skills, target sectors/employers, visa status, availability.
This file drives the LLM scoring rubric and every résumé/cover-letter summary line.

### 2. Your master résumé — `skill/master_resume.yml` (create it)
```bash
cp "Job automation/skill/master_resume.example.yml" "Job automation/skill/master_resume.yml"
```
Replace every field with your real education, experience bullets, and skills — this is the
superset the tailoring step selects and re-emphasizes from per job. It's gitignored, so it
never gets committed. **Do not just edit the `.example.yml` in place**: `tailor.py` and
`SKILL.md` read `master_resume.yml` (no `.example`), and the example currently contains
Vallabh's real data as a "sample," not a blank template.

### 3. Your secrets/contact info — `skill/secrets.yml` (create it)
```bash
cp "Job automation/skill/secrets.example.yml" "Job automation/skill/secrets.yml"
```
Fill in your name, email, phone, LinkedIn/GitHub, visa status, and the path to your résumé
PDF (used for form pre-fill). Also gitignored. Optionally add your own free API keys
(Adzuna, RapidAPI/JSearch) if you want those sources active.

### 4. Your real résumés (writing-voice source) — `skill/sources_resumes/`
This folder is referenced everywhere (`house-style`, `style-reviewer`) but is **gitignored**
(PII) and not present in the repo. Create it and drop in 1-3 of your own real résumé PDFs:
```bash
mkdir -p "Job automation/skill/sources_resumes"
# copy Resume_*.pdf here
```
The writing skills read these to learn *your* voice (verbs, formatting, bullet style).

### 5. Company/portal watchlist — `skill/companies.yml`
Currently ~60 fuel-cell/hydrogen employers across aviation/rail/heavy-vehicle sectors
(DLR, Airbus, Alstom, Daimler Truck, Bosch, cellcentric, Fraunhofer, etc.). Replace with
companies in **your** target industry. Keep the same YAML shape
(`name`, `portal: greenhouse|lever|ashby|smartrecruiters|custom`, `careers_url`, `sectors`,
optional `query`). `portal: custom` entries need their ATS/token verified on first live run
(the file says so already — same caveat applies to whatever you add).

### 6. Search config — `skill/config.yml`
Everything in here is fuel-cell-specific and needs replacing:
- `jobspy.search_terms` — currently `"fuel cell engineer"`, `"Brennstoffzelle"`, etc.
- `aggregators.adzuna.what`, `.arbeitnow.query`, `.bundesagentur.queries`, `.euraxess.query`
- `include_keywords` / `exclude_keywords` — the hard prefilter rules
- `locations` — currently Stuttgart-first; change to your preferred geography
- `delivery.gmail.to` — **currently hardcoded to `saibharadhwajreddy@gmail.com`**, change
  to your own address or the digest will email the wrong person
- `candidate.visa_status`, `candidate.german_level` — quick-facts used in cover letters

### 7. Writing-voice skills — `skills/house-style/`, `skills/resume-writer/`,
   `skills/cover-letter-writer/`, `skills/application-writer/`, `skills/style-reviewer/`
These are the most personalized files in the repo. `house-style/SKILL.md` is explicitly
titled "write like Vallabh, not like an AI" and hardcodes:
- His name, and instructions to match voice from `skill/sources_resumes/`
- Example bullets with his real tools (ANSYS ACP, MATLAB/Simulink, DMLS) and numbers
  (80% efficiency, 25 kg mass reduction, Shell Eco-Marathon)
- His banned-phrase list and em-dash rule (the em-dash/AI-tell rules are generic and worth
  keeping; the *examples* are not)

Two options:
- **Cheap fix:** leave the mechanics (structure, ATS hygiene, no-em-dash/no-AI-cliché rules,
  the self-check loop) as-is — they're good practice for anyone — and just accept the example
  bullets are illustrative. The agent will still pull real content from *your*
  `master_resume.yml` and `sources_resumes/`, so output won't actually contain Vallabh's
  experience. Least effort, slightly confusing to read.
- **Proper fix (recommended):** re-run the "reverse-engineer voice from résumés" step for
  yourself — ask an agent to read your `sources_resumes/*.pdf` and rewrite
  `house-style/SKILL.md`'s examples/verb list/banned phrases to match *your* real writing,
  the same way this was originally built for Vallabh. Also swap "Vallabh" → your name and
  the DLR/Bosch/Ecogenium example references in `resume-writer/SKILL.md`,
  `cover-letter-writer/SKILL.md`, and `style-reviewer/AGENT.md`.

### 8. One hardcoded prompt string — `skill/jobauto/tailor.py:64`
The cover-letter tailoring instruction literally says *"references the candidate's
DLR/Bosch/Ecogenium fuel-cell work"*. Harmless if you skip it (the agent has your real
`master_resume.yml` in front of it and won't invent DLR experience you don't have), but for
correctness, edit that instruction string to reference your own background instead.

### 9. Dashboard branding — `skill/jobauto/static_dashboard.py`
Title/header text ("Fuel-Cell Job Radar — Vallabh Pataneni", "scored against Vallabh's
profile...") is hardcoded around lines 77 and 180-182. Cosmetic only — change the strings if
you want the dashboard to say your name/field instead.

### 10. Stale historical data — reset before your first run
These files hold Vallabh's actual search history/results and will confuse your dashboard and
scoring cache if left in place:
```bash
cd "Job automation"
rm -rf applications/*                       # his 3 example applications
rm -f reports/*.md                          # his daily digests
rm -f dashboard/latest_jobs.json dashboard/seen.json dashboard/source_check.json
rm -f dashboard/dashboard.html dashboard/auto_latest.html
rm -rf skill/jobs.db skill/output           # local pipeline state, if present (gitignored)
```
They'll regenerate cleanly on your first `fetch`/`report` run. Also delete
`TASKS.md`/`DISCUSSION.md`/`PLAN.md` content that's specific to his search decisions if you
want a clean planning doc (optional — these are just working notes).

### 11. Repo-level infra (if you fork rather than get direct push access)
- The GitHub Action commits back to `Job automation/reports` and `dashboard/` — it needs
  `contents: write` on **your own repo**, so fork this repo (don't just read someone else's).
- Repo secrets `RAPIDAPI_KEY`, `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` are optional (aggregators
  degrade gracefully without them) — add your own free-tier keys under your fork's
  **Settings → Secrets and variables → Actions** if you want those sources active.
- If you plan to run stages 3+ (scoring/tailoring/pre-fill) via OpenClaw instead of Claude
  Code, `skill/install.sh` symlinks `skill/` into `~/.openclaw/workspace/skills/` — see
  `skill/SKILL.md` for the cron + Gmail wiring on that path.

---

## Recommended order of operations

1. Fork/clone the repo; confirm GitHub Actions is enabled.
2. Rewrite `profile.md`.
3. Create `skill/master_resume.yml` and `skill/secrets.yml` from the `.example` files.
4. Drop your real résumé PDFs into `skill/sources_resumes/`.
5. Replace `skill/companies.yml` with your target companies.
6. Edit `skill/config.yml` (search terms, keywords, locations, `delivery.gmail.to`).
7. Reset the stale data (`applications/`, `reports/`, `dashboard/*.json|*.html`).
8. (Recommended) regenerate `skills/house-style/SKILL.md` from your own résumés; swap the
   name/example references in the other `skills/` files.
9. Run a manual check: `cd "Job automation/skill" && pip install -r requirements.txt &&
   python -m jobauto check-sources` — confirms your `companies.yml` tokens actually resolve
   before you wait for the next cron.
10. Manually trigger the workflow once (**Actions → Daily Job Discovery → Run workflow**)
    and check the new `reports/<today>.md` and `dashboard/auto_latest.html` reflect your
    field, not fuel cells.
11. Start an agent session (Claude Code or OpenClaw) and ask it to score/tailor/apply for
    the newly discovered jobs — that part isn't on a cron yet, by design (human-in-the-loop).
