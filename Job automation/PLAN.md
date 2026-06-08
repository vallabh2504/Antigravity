# Job Automation — Build Plan (v1)

> Status: **Plan / awaiting approval + Openclaw confirmation.**
> Last updated: 2026-06-08.
> Scope decided with the user: **Full 7-stage pipeline incl. form pre-fill**, runs **every morning**,
> delivers via **email/Gmail digest + Markdown report in repo + web dashboard**, LLM scoring via the
> user's **Openclaw agent (ChatGPT OAuth)** if compatible.

---

## 0. Important: the "Openclaw" integration (need to confirm)

The user wants this to run on their existing **Openclaw** setup and reuse its **ChatGPT OAuth** for LLM
calls. I don't have verified knowledge of a tool by that exact name, so the design treats Openclaw as a
**pluggable provider** behind two interfaces. The system works as long as Openclaw can supply:

| Need | What it must expose | If yes | If no (fallback) |
|------|--------------------|--------|------------------|
| **Scheduling** | A daily cron / timed trigger that can run a script | Openclaw triggers `daily_run` | **GitHub Actions cron** (`.github/workflows/daily.yml`) |
| **LLM access** | An HTTP endpoint for chat completions (ideally OpenAI-compatible) using its ChatGPT OAuth | `LLMClient` points at Openclaw's endpoint | Anthropic API key, or rules-only mode |
| **Runtime** | Ability to run **Python 3.11+** and **Playwright** (headless Chromium) for stage 4 pre-fill | Run everything on Openclaw | GitHub Actions runner / small VPS |
| **Secrets** | Somewhere to store credentials (SMTP, API keys, profile) | Use Openclaw's secret store | GitHub Actions secrets / `.env` (gitignored) |

> **Questions for the user are in §11.** Until these are answered, scheduler + LLM are stubbed behind
> interfaces so nothing about the core pipeline depends on the final choice.

---

## 1. Goals & non-goals

**Goal:** Every morning, automatically discover fresh fuel-cell roles & PhD positions (aviation > rail >
heavy vehicles; Stuttgart → Germany → Europe), rank them against `profile.md`, draft tailored docs,
**pre-fill** application forms up to the submit button, track everything, and deliver a digest the user
reviews over coffee.

**Non-goals (deliberate):**
- **No auto-submitting** applications. The system pre-fills and stops at the submit button — a human
  clicks send. (ToS, quality, and anti-bot reasons. See §8.)
- **No mass-blasting.** Win = better targeting + faster tailoring, not 500 spray applications.
- **No "scrape the entire internet" literally.** That's neither legal nor reliable. We get broad
  coverage via official ATS APIs + job-board APIs + RSS + a *polite, targeted* set of company career
  pages. See §4.

---

## 2. The 7 stages → modules

```
1 Discover ──► 2 Normalize/Dedupe ──► 3 Score/Rank ──► 4 Review queue (HUMAN) ──┐
                                                                                 │ approved
                          ┌──────────────────────────┬───────────────────────────┤
                          ▼                           ▼                           ▼
                   5 Tailor docs              6 Pre-fill forms             7 Track + follow-up
                   (resume/cover)             (Playwright, stop           (DB + reminders +
                                               at submit)                  digest delivery)
```

| # | Stage | Module | What it does |
|---|-------|--------|--------------|
| 1 | Discovery | `sources/` | One adapter per source. Pulls raw postings. |
| 2 | Normalize | `normalize.py` | Parse → common schema, dedupe by content hash. |
| 3 | Score/Rank | `score.py` + `llm.py` | Hard rules filter, then LLM fit score (0–100 + rationale) vs `profile.md`. |
| 4 | Review | dashboard + digest | Human approves/rejects. **The gate.** |
| 5 | Tailor | `tailor.py` | LLM drafts resume bullet emphasis + cover letter per approved job. |
| 6 | Pre-fill | `apply/prefill.py` | Playwright opens the application, fills known fields, **pauses at submit**. |
| 7 | Track | `db.py` + `notify.py` | Pipeline DB, follow-up reminders, builds the daily digest. |

---

## 3. Discovery sources (stage 1) — coverage strategy

**Tier A — Official ATS APIs (clean, ToS-friendly, primary):** per-company JSON boards.
- Greenhouse: `boards-api.greenhouse.io/v1/boards/<company>/jobs`
- Lever: `api.lever.co/v0/postings/<company>`
- Ashby, Workable, SmartRecruiters, Personio (big in DE), Join.com.
- We maintain a **`companies.yml`** watchlist (H2FLY, cellcentric, Daimler Truck, Bosch, Airbus, MTU,
  Alstom, Siemens Mobility, ZeroAvia, Ballard, Cummins/Accelera, Freudenberg, Symbio, …).

**Tier B — Job-board / aggregator APIs & feeds (breadth):**
- **Adzuna API** (Germany), **Arbeitnow API**, **Jobicy**, **RemoteOK**, **WeWorkRemotely RSS**.
- **EURAXESS** + university portals for **PhD positions** (DLR, Fraunhofer ISE/ICT, KIT, Uni Stuttgart,
  RWTH, FZ Jülich), **academics.com**, **stellenwerk**.
- **Bundesagentur für Arbeit** (German federal jobs API) for DE breadth.

**Tier C — Targeted page fetch (last resort, polite):** for a few key career pages with no API, a gentle
scheduled fetch with caching + backoff. **No LinkedIn/Indeed scraping** (ToS + anti-bot). For those, rely
on their *email alerts* forwarded into the inbox the system already reads.

Each source is an adapter implementing:
```python
class Source(Protocol):
    name: str
    def fetch(self, queries: list[Query]) -> list[RawPosting]: ...
```
Adding a source = adding one file. Sources are enabled/disabled in `config.yml`.

---

## 4. Scoring & ranking (stages 2–3)

1. **Hard rules** (cheap, drop obvious misses): keyword match (fuel cell / hydrogen / FCEV / PEM / stack /
   BoP …), sector tags (aviation/rail/heavy), location in {Stuttgart, DE, EU}, role type (job vs PhD).
2. **Soft LLM score** via `LLMClient` (Openclaw/ChatGPT → fallback Anthropic): feeds the posting + a
   compact form of `profile.md`, returns JSON `{score: 0-100, reasons: [...], german_required: bool,
   visa_friendly_guess: bool, tier: A/B/C}`. **Cached by job hash** so we never re-score the same posting.
3. **German-level handling:** A2–B1 → roles needing B2+ are *flagged*, not discarded (per profile).

---

## 5. Tailoring (stage 5)

- `master_resume.yml` (structured) + `cover_letter_base.md` live in the repo (gitignored if you prefer).
- For each **approved** top-N job, the LLM produces: (a) reordered/highlighted resume bullets, (b) a
  tailored cover-letter draft, (c) a 3-line "why me / why them." Saved to `output/<job_id>/`.
- **Human edits & owns** the final document. Nothing is sent automatically.

---

## 6. Pre-fill / application assist (stage 6)

- **Playwright** (headless or headful) opens the application URL, detects the ATS (Greenhouse/Lever/Ashby
  have predictable forms), and fills name, email, phone, links, resume upload, and common questions from
  `profile.md` + tailored docs.
- **Hard stop at the submit button.** It screenshots the filled form, saves session state, and the digest
  links you straight to it to review & click send yourself.
- Realistic coverage: smooth on standard ATSes (~Tier A), partial/skip on custom portals. Logged honestly
  per job ("pre-filled" / "manual — custom portal").
- **Risk note:** even pre-fill automation can trip anti-bot on some sites; adapters run gently, with human
  fallback. We never defeat CAPTCHAs or auth walls.

---

## 7. Tracking & delivery (stage 7)

- **DB:** SQLite (`jobs.db`) with states `discovered → scored → approved/rejected → docs_ready →
  prefilled → applied → screen → onsite → offer → closed`. Committed? No — DB is gitignored; reports are
  committed.
- **Follow-up reminders:** e.g. nudge 7 days after `applied`.
- **Delivery (all three, per user):**
  1. **Email/Gmail digest** — ranked shortlist each morning (top matches, scores, links, pre-fill status).
  2. **Markdown report in repo** — `Job automation/reports/YYYY-MM-DD.md`, committed daily (version-controlled history).
  3. **Web dashboard** — a small FastAPI (or Next.js) app showing the pipeline & ranked jobs, deployable to Vercel; reads `jobs.db`/JSON.

---

## 8. Proposed repo layout

```
Job automation/
├── README.md                 # overview (done)
├── DISCUSSION.md             # design discussion (done)
├── profile.md                # candidate profile (done)
├── PLAN.md                   # this file
├── config.yml                # enabled sources, queries, thresholds, schedule
├── companies.yml             # ATS watchlist
├── pyproject.toml            # deps (httpx, pydantic, playwright, jinja2, fastapi…)
├── src/jobauto/
│   ├── run.py                # `daily_run` entrypoint orchestrating all 7 stages
│   ├── models.py             # RawPosting, Job, Score (pydantic)
│   ├── sources/              # one adapter per source (greenhouse.py, lever.py, adzuna.py, euraxess.py…)
│   ├── normalize.py          # parse + dedupe
│   ├── llm.py                # LLMClient: Openclaw → Anthropic → rules-only
│   ├── score.py              # rules + LLM scoring
│   ├── tailor.py             # resume/cover drafting
│   ├── apply/prefill.py      # Playwright pre-fill
│   ├── db.py                 # SQLite pipeline
│   └── notify.py             # email + markdown report builders
├── dashboard/                # web UI (FastAPI/Next.js)
├── reports/                  # YYYY-MM-DD.md (committed daily)
├── output/                   # tailored docs, screenshots (gitignored)
└── .github/workflows/daily.yml  # cron fallback if not using Openclaw
```

---

## 9. Tech stack
- **Python 3.11+**, `httpx` (async fetch), `pydantic` (models), `PyYAML`, `jinja2` (report/email templates),
  `playwright` (pre-fill), `sqlite3`, `fastapi`+`uvicorn` (dashboard).
- **LLM:** OpenAI-compatible client pointed at Openclaw's ChatGPT endpoint (fallback Anthropic SDK / rules).
- **Email:** SMTP (or the session's Gmail integration to drop a draft/message).

---

## 10. Build milestones (incremental — each ships something usable)

- **M1 — Skeleton + discovery (Tier A + Adzuna + EURAXESS):** fetch → normalize → dedupe → SQLite. Output a
  plain Markdown report. *(Useful day 1: real fresh listings, deduped.)*
- **M2 — Scoring:** rules filter + LLM fit scores via `LLMClient`. Ranked report. Email digest.
- **M3 — Daily automation:** wire `daily_run` to Openclaw schedule (or GitHub Actions cron) + secrets.
- **M4 — Tailoring:** master resume/cover + per-job drafts for top matches.
- **M5 — Pre-fill:** Playwright adapters for Greenhouse/Lever/Ashby, stop-at-submit + screenshots.
- **M6 — Dashboard:** FastAPI/Next.js UI, optional Vercel deploy.
- **M7 — Follow-ups & polish:** reminders, more sources, tuning.

---

## 11. Open questions (blocking the build)

**About Openclaw (decisive for scheduler + LLM + runtime):**
1. What *is* Openclaw here — a self-hosted agent? Can you share a docs link or one line on what it runs?
2. Can it **run on a daily schedule/cron** and execute a **Python script** (+ install Playwright)?
3. Does its **ChatGPT OAuth** expose an **HTTP endpoint** I can call for chat completions (and is it
   OpenAI-API-compatible)? If not, I'll use it differently or fall back to an Anthropic key.
4. Does it have a **secret store** for SMTP creds / API keys?
   *(If any answer is "no", we use the GitHub Actions cron + secrets fallback — equally fine.)*

**About delivery & data:**
5. **Email:** which address for the digest (default: your Gmail), and should it be a *sent email* or a
   *Gmail draft* you review?
6. **Dashboard:** OK to deploy to **Vercel** (public URL with light auth), or keep it local-only?
7. **Resume:** can you drop your current **CV (PDF) + a plain-text version** into the folder so tailoring
   and pre-fill have real content? (PII like phone/address can stay in a gitignored `secrets.yml`.)
8. **Visa line for cover letters / filters:** your permit status + EU Blue Card eligibility (still open in `profile.md`).

---

## 12. My recommendation
Approve **M1–M3 first** (discovery + ranking + daily email/report) so you get value within the first build,
then layer M4–M6 (tailoring, pre-fill, dashboard). I'll start M1 the moment you confirm the Openclaw
answers in §11 (or tell me to use the GitHub Actions fallback).
