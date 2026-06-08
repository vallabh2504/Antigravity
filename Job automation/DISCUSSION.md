# Job Automation — Design Discussion

This doc captures the decisions we need to make. I've laid out the landscape and my
recommendations; the questions at the bottom are the ones I need your input on.

---

## 1. The pipeline, stage by stage

### Stage 1 — Discovery (find the postings)
**Approaches, easiest → hardest:**
- **Official APIs** (best): Greenhouse, Lever, Ashby, Workable all expose public
  JSON endpoints per company (e.g. `boards-api.greenhouse.io/v1/boards/<co>/jobs`).
  Clean, ToS-friendly, no scraping.
- **Job board APIs / feeds**: Adzuna, USAJobs, RemoteOK, WeWorkRemotely RSS,
  Hacker News "Who is hiring" threads.
- **Aggregator scraping** (LinkedIn, Indeed): high coverage but ToS-restricted and
  brittle. Risky — use sparingly or rely on their email alerts instead.

**My recommendation:** Start with Greenhouse/Lever/Ashby APIs for a target list of
companies + Adzuna for breadth. Avoid scraping LinkedIn directly.

### Stage 2 — Filter & rank
- Hard rules first (location, visa, comp floor, seniority, keywords) to cheaply drop
  obvious misses.
- Then an **LLM scorer** that reads each posting + your profile and returns a
  0–100 fit score with a one-line rationale. Cache by job hash.

### Stage 3 — Tailor documents
- Maintain a **master resume** (structured, e.g. JSON/YAML) and a base cover letter.
- LLM generates a tailored variant per job, emphasizing relevant experience.
- **Human approves** before anything leaves your machine.

### Stage 4 — Submit
- **Auto-fill where safe**: some ATSes allow programmatic-ish submission, but most
  require a browser. Tools like Playwright can fill forms, but auto-submitting at
  scale violates many ToS and can get you flagged.
- **Pragmatic stance:** automate *up to the submit button* (pre-fill everything),
  let you click send. This keeps the 80% benefit without the legal/quality risk.

### Stage 5 — Track & follow up
- A pipeline DB (SQLite to start) with states: `discovered → reviewed → applied →
  screen → onsite → offer → closed`.
- Auto-reminders for follow-ups (e.g. nudge 7 days after applying).

### Stage 6 — Interview prep
- On state change to `screen`, auto-generate a company brief (news, product, recent
  funding) + likely interview questions for the role.

### Stage 7 — Networking
- Draft (don't send) personalized outreach to recruiters / referrals.

---

## 2. Tech stack options

| Concern | Lightweight | Robust |
|--------|-------------|--------|
| Language | Python | Python + typed models |
| Storage | SQLite + JSON | Postgres |
| Scheduling | cron | Airflow / Prefect / Temporal |
| LLM | Claude API | Claude API + eval harness |
| Browser automation | Playwright | Playwright + stealth (risky) |
| UI / review | CLI + markdown | Web dashboard (FastAPI + React) |
| Notifications | Email / Slack webhook | Same |

**My default recommendation for a v1:** Python + SQLite + Claude API + a simple CLI
or local web review queue + cron. Ship something useful in days, not weeks.

---

## 3. Hard truths / risks
- **ToS & legality:** Scraping and auto-applying can violate platform terms. Lean on
  official APIs and human-in-the-loop submission.
- **Quality vs. volume:** Spray-and-pray applications hurt you. The win is *better
  targeting and faster tailoring*, not blasting 500 applications.
- **Rate limits & blocking:** Aggressive scraping gets IPs banned. Be gentle.
- **Data privacy:** Your resume/PII stays local; be careful what you send to APIs.

---

## Questions for you

1. **What roles/locations are you targeting?** (titles, seniority, remote vs.
   on-site, countries) — this drives the source list and filters.
2. **How aggressive on submission?** Pre-fill + you click send (safe), or
   attempt true auto-submit (riskier)?
3. **What's the desired interface?** CLI, local web dashboard, a spreadsheet, or
   notifications into Slack/email/Telegram?
4. **Build vs. buy:** do you want a custom system here, or me to evaluate existing
   tools (e.g. Simplify, LazyApply, Huntr) and just automate the gaps?
5. **Scope for v1:** which single stage would give you the most relief right now —
   discovery+ranking, or tailoring docs?
