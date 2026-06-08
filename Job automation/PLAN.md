# Job Automation — Build Plan (v3, built & runnable)

> Status: **v1 BUILT and validated end-to-end in-container.** Agent-triggered (no cron yet) —
> hand the `skill/` folder to OpenClaw, which adds the morning cron.
> Last updated: 2026-06-08.
> Scope (decided with user): **Full 7-stage pipeline incl. form pre-fill**, runs **every morning** (cron
> added by OpenClaw), delivers via **email/Gmail digest + Markdown report in repo + web dashboard**, LLM
> via the user's **OpenClaw** ChatGPT OAuth.

## Build status (what exists in `skill/`)
| Stage | Status | Where |
|-------|--------|-------|
| 1 Discover | ✅ portal recipes (Greenhouse/Lever/Ashby/SmartRecruiters/Workday/custom) + agent-fetch + httpx backends | `jobauto/sources/`, `cli manifest`/`fetch` |
| 2 Normalize/Dedupe | ✅ HTML-strip, content-hash dedupe, SQLite store | `normalize.py`, `db.py` |
| 3 Score/Rank | ✅ rules prefilter + LLM-scoring exchange (agent scores) | `score.py`, `cli to-score`/`apply-scores` |
| 4 Review gate | ✅ digest + `approve`/`reject` | `digest.py`, `cli report`/`approve` |
| 5 Tailor | ✅ curated-per-JD resume + cover letter | `tailor.py`, `cli to-tailor`/`apply-tailor` |
| 6 Pre-fill | ✅ task builder + OpenClaw-browser runbook + Playwright fallback (stops at submit) | `apply_prefill.py`, `cli to-prefill` |
| 7 Track/Deliver | ✅ pipeline states, follow-ups, daily report; Gmail/messaging wired via OpenClaw | `db.py`, `digest.py` |
| Cron | ⏳ OpenClaw adds it (host must be awake AM) | `SKILL.md > Cron` |
| Dashboard | ⏳ not yet (M6) | `dashboard/` |

**Validated run** (sample fixture, since this container's egress blocks live portals):
`ingest 7 → rules drop 1 → score 6 → digest top-6 → approve 2 → tailor 2 → docs_ready`. See
`reports/2026-06-08.md`. On OpenClaw (unblocked) `cli fetch` pulls the real postings.

## How it runs now vs. on OpenClaw
- **Now (this container / on demand):** you ask → the agent runs the `cli` steps, fetching via web/browser
  tools (egress to job APIs is blocked here, so it uses the `manifest`→fetch→`ingest` backend) and doing the
  LLM scoring/tailoring itself. No secrets needed.
- **On OpenClaw (after handoff):** `bash skill/install.sh` symlinks it in; OpenClaw's model does scoring/
  tailoring via your ChatGPT OAuth, its browser does pre-fill, Gmail/Telegram deliver the digest, and a
  cron fires it each morning.

---

## 0. What changed: this is now an OpenClaw *skill*, not a standalone app

[OpenClaw](https://github.com/openclaw/openclaw) (Peter Steinberger's local, open-source AI assistant —
formerly Clawde/Moltbot) already provides a scheduler, an LLM, a browser, email, and messaging. So we do
**not** rebuild any of that. The job automation is implemented as a **native OpenClaw skill** plus a few
helper Python scripts, triggered by an OpenClaw **cron job**.

| Stage need | OpenClaw primitive we use | What we DON'T build |
|---|---|---|
| Daily morning trigger | **Cron jobs** | ~~GitHub Actions / custom cron~~ |
| Orchestration / reasoning | A **skill**: `~/.openclaw/workspace/skills/job-automation/SKILL.md` | ~~bespoke orchestrator~~ |
| Run fetchers / scripts | **`bash` / `process`** tools | ~~job runner~~ |
| Stage 6 form pre-fill | Built-in **browser tool** (+ Playwright fallback) | ~~separate browser stack~~ |
| Stage 3 & 5 LLM (scoring, tailoring) | **`agent.model`** = your ChatGPT OAuth | ~~API key / LLM client~~ |
| Stage 7 delivery | **Gmail (Pub/Sub)** + messaging channels (Telegram/WhatsApp) | ~~SMTP server~~ |
| Memory / tracking | OpenClaw workspace memory + local **SQLite** | — |
| Secrets/config | `~/.openclaw/openclaw.json` + skill config + gitignored `secrets.yml` | ~~secret manager~~ |

**Relevant OpenClaw facts (from its repo/docs):**
- Skills live at `~/.openclaw/workspace/skills/<skill>/SKILL.md` (Markdown-defined, like Claude Code skills);
  tools include `bash`, `process`, `read`, `write`, `edit`, plus first-class **browser**, **canvas**, nodes,
  sessions.
- Automations: **Cron jobs** and **Webhooks**. Email via **Gmail Pub/Sub**.
- LLM via OAuth subscriptions incl. **OpenAI (ChatGPT/Codex)**, set as `agent.model = "<provider>/<model-id>"`
  in `~/.openclaw/openclaw.json`.
- Session context files: `AGENTS.md`, `SOUL.md`, `TOOLS.md`.

> **Fallback (only if needed):** if you'd rather not run it inside OpenClaw, a `.github/workflows/daily.yml`
> cron + an LLM key reproduces the same pipeline. OpenClaw is the primary target.

> **Security note:** OpenClaw runs with broad permissions (email, browser, shell). This skill stays within
> that model but is scoped: it only *reads* job sources, *drafts* docs, and *pre-fills* forms — it never
> auto-submits, never handles your passwords, and writes only inside its own skill/workspace dirs.

---

## 1. Goals & non-goals

**Goal:** Every morning OpenClaw automatically discovers fresh fuel-cell roles & PhD positions
(aviation > rail > heavy vehicles; Stuttgart → Germany → Europe), ranks them against `profile.md`, drafts
tailored docs, **pre-fills** application forms up to the submit button, tracks everything, and sends you a
digest to review over coffee.

**Non-goals (deliberate):**
- **No auto-submitting.** Pre-fill stops at the submit button; a human clicks send (ToS, quality, anti-bot).
- **No mass-blasting.** Win = better targeting + faster tailoring, not 500 spray applications.
- **No "scrape the entire internet" literally.** Broad coverage via official ATS APIs + job-board/PhD APIs +
  RSS + polite targeted fetches. **No LinkedIn/Indeed scraping** — use their email alerts (OpenClaw reads Gmail).

---

## 2. The 7 stages → how each runs in OpenClaw

```
CRON (every morning) ──► SKILL: job-automation
  1 Discover ─► 2 Normalize/Dedupe ─► 3 Score/Rank ─► 4 Review (HUMAN via digest) ─┐
                                                                                    │ you approve
                              ┌──────────────────────┬─────────────────────────────┤  (reply in chat)
                              ▼                       ▼                             ▼
                       5 Tailor docs          6 Pre-fill (browser)          7 Track + deliver
                       (agent.model)          stop at submit                (SQLite + Gmail/Telegram + report)
```

| # | Stage | Implemented as | Detail |
|---|-------|----------------|--------|
| 1 | Discover | `scripts/discover.py` via `bash` tool | Source adapters → raw postings (see §3). |
| 2 | Normalize | `scripts/normalize.py` | Parse → schema, dedupe by content hash, upsert SQLite. |
| 3 | Score/Rank | SKILL.md prompt + `agent.model` | Rules filter, then OpenClaw's LLM scores fit 0–100 + rationale vs `profile.md`. |
| 4 | Review | **digest + your reply** | OpenClaw messages you the shortlist; you approve/reject by replying (Telegram/WhatsApp/email/chat). |
| 5 | Tailor | SKILL.md + `agent.model` | LLM drafts tailored resume bullets + cover letter for approved jobs. |
| 6 | Pre-fill | **browser tool** (Playwright fallback) | Opens application, fills fields, screenshots, **pauses at submit**. |
| 7 | Track | `scripts/db.py` + OpenClaw Gmail/messaging | Pipeline states, follow-up reminders, builds + sends digest, commits report. |

OpenClaw's **agent** is the orchestrator: the cron fires → it reads `SKILL.md` → runs the scripts via
`bash`/`process` → uses its own model for stages 3 & 5 → uses browser for stage 6 → sends digest via Gmail/
messaging. The Python scripts are deterministic plumbing; the LLM reasoning is OpenClaw's job.

---

## 3. Discovery sources (stage 1)

**Tier A — Official ATS APIs (primary, ToS-clean):** per-company JSON boards.
- Greenhouse `boards-api.greenhouse.io/v1/boards/<co>/jobs`, Lever `api.lever.co/v0/postings/<co>`,
  Ashby, Workable, SmartRecruiters, **Personio** (big in DE), Join.com. Watchlist in **`companies.yml`**
  (H2FLY, cellcentric, Daimler Truck, Bosch, Airbus, MTU, Alstom, Siemens Mobility, ZeroAvia, Ballard,
  Cummins/Accelera, Freudenberg, Symbio…).

**Tier B — Job-board / PhD APIs & feeds (breadth):** Adzuna (DE), Arbeitnow, Jobicy, RemoteOK,
WeWorkRemotely RSS, **Bundesagentur für Arbeit** API; **EURAXESS**, academics.com, stellenwerk, plus DLR /
Fraunhofer / KIT / Uni Stuttgart / RWTH / FZ Jülich portals for **PhDs**.

**Tier C — Polite targeted fetch / Gmail alerts:** a few key career pages via gentle cached fetch; for
LinkedIn/Indeed, set up their email alerts → OpenClaw's Gmail reader ingests them. No scraping of anti-bot sites.

Each source = one adapter file in `scripts/sources/` implementing `fetch(queries) -> list[RawPosting]`.
Enable/disable in `config.yml`.

---

## 4. Scoring (stage 3) & German handling
1. **Hard rules:** fuel-cell/H2 keywords, sector tags, location ∈ {Stuttgart, DE, EU}, job-vs-PhD.
2. **LLM score (OpenClaw `agent.model`):** posting + compact `profile.md` → JSON `{score, reasons[],
   german_required, visa_friendly_guess, sector, tier}`. **Cached by job hash.**
3. **German A2–B1:** roles needing B2+ are *flagged*, not dropped (per profile).

---

## 5. Tailoring (stage 5)
- `master_resume.yml` + `cover_letter_base.md` in the skill dir (PII in gitignored `secrets.yml`).
- Per approved top-N job, OpenClaw drafts: highlighted resume bullets, a tailored cover letter, a 3-line
  "why me / why them." Saved to `output/<job_id>/`. **You edit & own the final.**

---

## 6. Pre-fill (stage 6)
- OpenClaw's **browser tool** opens the application URL, detects the ATS, fills name/email/phone/links/
  resume + common questions from `profile.md` + tailored docs, screenshots, and **stops at submit**.
- Standard ATSes (Tier A) pre-fill smoothly; custom portals are logged as "manual." Never defeats CAPTCHAs
  or auth walls. Playwright is a fallback only if the built-in browser can't handle a form.

---

## 7. Tracking & delivery (stage 7)
- **SQLite** `jobs.db` (gitignored): states `discovered → scored → approved/rejected → docs_ready →
  prefilled → applied → screen → onsite → offer → closed`; follow-up reminders (e.g. nudge 7 days post-apply).
- **Delivery (all three):**
  1. **Gmail digest** (OpenClaw) — ranked shortlist each morning: top matches, scores, links, pre-fill status.
  2. *(bonus)* **Messaging digest** — same to **Telegram/WhatsApp** so you can approve by reply.
  3. **Markdown report** committed to `Job automation/reports/YYYY-MM-DD.md` (version-controlled history).
  4. **Web dashboard** — small FastAPI/Next.js app over `jobs.db`, deployable to Vercel (optional).

---

## 8. Repo layout (the skill lives here; symlink/sync into OpenClaw workspace)

```
Job automation/
├── README.md  DISCUSSION.md  profile.md  PLAN.md      # (done)
├── skill/                         # → symlinked to ~/.openclaw/workspace/skills/job-automation/
│   ├── SKILL.md                   # the OpenClaw skill (orchestration + LLM prompts)
│   ├── config.yml                 # enabled sources, queries, thresholds, schedule, delivery targets
│   ├── companies.yml              # ATS watchlist
│   ├── secrets.example.yml        # template (real secrets.yml is gitignored)
│   └── scripts/
│       ├── discover.py            # stage 1 (calls sources/*)
│       ├── sources/               # greenhouse.py, lever.py, adzuna.py, euraxess.py, …
│       ├── normalize.py           # stage 2
│       ├── db.py                  # SQLite pipeline (stage 7 storage)
│       ├── digest.py              # builds digest + writes daily report
│       └── prefill.py             # Playwright fallback for stage 6
├── dashboard/                     # optional web UI (stage 4/7)
├── reports/                       # YYYY-MM-DD.md committed daily
└── output/                        # tailored docs + screenshots (gitignored)
```
The repo is the source of truth; the user symlinks `skill/` into `~/.openclaw/workspace/skills/` (or points
OpenClaw at this git checkout). An OpenClaw **cron job** calls the skill each morning.

---

## 9. Tech stack
- **OpenClaw** (scheduler, LLM via ChatGPT OAuth, browser, Gmail, messaging).
- **Python 3.11+** helper scripts: `httpx`, `pydantic`, `PyYAML`, `jinja2`, `sqlite3`; `playwright` only as
  browser fallback; `fastapi`+`uvicorn` for the optional dashboard.

---

## 10. Build milestones (each ships something usable)
- **M1 — Skill skeleton + discovery:** `SKILL.md` + `discover.py` (Greenhouse/Lever + Adzuna + EURAXESS) →
  normalize → dedupe → SQLite → plain Markdown report. *(Day-1 value: real fresh, deduped listings.)*
- **M2 — Scoring & digest:** rules + OpenClaw LLM fit scores; ranked digest delivered via Gmail/Telegram.
- **M3 — Cron:** register the OpenClaw cron job; verify a real morning run end-to-end.
- **M4 — Tailoring:** master resume/cover + per-job drafts for approved matches.
- **M5 — Pre-fill:** OpenClaw browser flows for Greenhouse/Lever/Ashby; stop-at-submit + screenshots.
- **M6 — Dashboard:** FastAPI/Next.js UI, optional Vercel deploy.
- **M7 — Follow-ups & polish:** reminders, more sources, tuning.

---

## 11. Open questions (to start the build)
1. **OpenClaw version/host:** which OS/machine runs it, and is it always-on in the mornings? (Cron only
   fires if the host is awake.)
2. **OpenClaw model:** what is `agent.model` set to (which ChatGPT model)? Confirms scoring/tailoring quality.
3. **Delivery channel for approvals:** Gmail only, or also **Telegram/WhatsApp** (lets you approve by reply)?
4. **Resume:** drop your current **CV (PDF + plain text)** into `skill/` so tailoring/pre-fill use real content.
5. **Dashboard:** OK to deploy to **Vercel** (light auth), or keep local-only?
6. **Visa line** for cover letters/filters: permit status + EU Blue Card eligibility (still open in `profile.md`).
7. **Workspace wiring:** can you symlink `skill/` into `~/.openclaw/workspace/skills/`, or should I add a
   tiny installer script that does it + registers the cron job?

---

## 12. Recommendation
Build **M1–M3 first** (discovery + scoring + a real daily OpenClaw cron digest) so you immediately get a
morning shortlist of fresh fuel-cell roles, then layer M4–M6 (tailoring, pre-fill, dashboard). I can start
M1 now — it needs no secrets, just your go-ahead. I'll wire the OpenClaw-specific bits (cron, model, Gmail)
once you confirm §11.
