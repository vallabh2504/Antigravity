---
name: job-automation
description: >
  Daily fuel-cell job & PhD search for the candidate in profile.md. Discovers fresh
  postings from company portals + aggregators, ranks them against the profile, drafts
  tailored resumes/cover letters, pre-fills application forms up to the submit button,
  tracks everything, and delivers a morning digest. Trigger on a morning cron, or on
  demand when the user asks "check for jobs" / "run the job search".
tools: [bash, process, read, write, edit, browser]
---

# Job Automation skill

You (the agent) are the orchestrator. Deterministic plumbing lives in the `jobauto`
Python package; you do the two things that need intelligence + network: **fetching
portals** and **LLM scoring/tailoring**. Run everything from this skill directory.

## Setup (first run)
```bash
pip install -r requirements.txt        # PyYAML (+ httpx for direct fetch)
```

## Not sure what to do? Ask the pipeline
```bash
python -m jobauto next     # inspects the DB and prints the exact next command to run
```
Run it anytime to self-orchestrate the stages below in order.
Config: `config.yml` (keywords, locations, delivery), `companies.yml` (portals to watch).
Candidate context: `../profile.md`, `master_resume.yml` (copy from the .example).
Secrets (applicant details, Adzuna keys): `secrets.yml` (copy from .example).

## The daily workflow — run these in order

### 1–2. Discover + ingest
First choose a backend:

**A) Direct (you have outbound network — the normal case on the user's machine):**
```bash
python -m jobauto fetch        # hits every portal in companies.yml + stores new jobs
```

**B) Agent-fetch (if Python can't reach the portals):**
```bash
python -m jobauto manifest     # writes output/manifest.json: the exact requests to make
```
Then for each entry, fetch the URL with your **browser/web tools** (and follow detail
links for full JD text). Also query the aggregators in `config.yml` (Adzuna, Arbeitnow,
EURAXESS, Bundesagentur) and ingest any **forwarded LinkedIn/Indeed job-alert emails**
from Gmail. Assemble results into `raw.json` (list of
`{company,title,location,url,jd_text,posted_at}`) then:
```bash
python -m jobauto ingest raw.json
```

### 3. Score
```bash
python -m jobauto to-score              # writes output/to_score.json (jobs + profile + rubric)
```
Read it, score each job per its `instructions` (0–100 fit, reasons, sector,
german_required, is_phd, tier), write `scores.json`, then:
```bash
python -m jobauto apply-scores scores.json
```

### 4. Deliver digest + human gate
```bash
python -m jobauto deliver               # report + output/digest_email.html/.txt/.short
```
`deliver` builds the artifacts and auto-sends via SMTP if creds are in secrets.yml;
otherwise YOU send `output/digest_email.html` via your own channel (OpenClaw Gmail/
Telegram, a Gmail MCP tool). Or open the **dashboard** (`dashboard/app.py`) to review
visually. The user replies `approve <id> <id>` or `reject <id>` (or clicks in the UI):
```bash
python -m jobauto approve <id> <id>
python -m jobauto reject <id>
```

### 5. Tailor (approved jobs)
```bash
python -m jobauto to-tailor             # writes output/to_tailor.json (FULL JD per job)
```
Draft per-posting `resume_markdown`, `cover_letter_markdown`, `why_fit` into `docs.json`
(curate to each JD; never invent experience), then:
```bash
python -m jobauto apply-tailor docs.json   # saves to output/<id>/, state -> docs_ready
python -m jobauto pdf                       # render resume.html/cover_letter.html -> upload-ready PDFs
```

### 6. Pre-fill (never submit)
```bash
python -m jobauto to-prefill            # writes output/to_prefill.json
```
For each job, open `apply_url` in the **browser tool**, fill fields from `applicant`
secrets + the tailored cover letter, upload the resume PDF, **screenshot, and STOP at
the submit button**. Never solve CAPTCHAs or pass logins. Then:
```bash
python -m jobauto set-state prefilled <id>
```
Tell the user which are ready to review-and-send.

### 7. Track / follow-up
State advances as the user reports back: `set-state applied|screen|onsite|offer|closed <id>`.
The next report surfaces `applied` jobs needing follow-up. If `delivery.commit_report`,
commit `reports/` to git each run.

## Cron (the user sets this up)
Register an OpenClaw **cron job** that runs this workflow each morning (e.g. 07:30). Until
then the user can simply ask you to run it on demand — same steps. The host must be awake
when the cron fires.

## Guardrails
- Never click submit / never auto-apply. Pre-fill only; the human sends.
- No scraping of LinkedIn/Indeed — use their email alerts via Gmail.
- Keep PII in `secrets.yml` (gitignored). Never commit `output/` or secrets.
- One bad source must not kill the run — skip and continue.
