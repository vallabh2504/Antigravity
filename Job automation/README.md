# Job Automation

A working space for designing a system that automates **80%+ of the job search** —
from discovery to application to follow-up — while keeping a human in the loop for
the decisions that actually matter.

## Goal

Reduce the manual, repetitive parts of job hunting (searching, filtering, tailoring,
applying, tracking) so your time goes to high-leverage work: networking,
interviewing, and final-call decisions.

## What can realistically be automated

| Stage | Automation potential | Notes |
|-------|---------------------|-------|
| 1. Discovery (finding postings) | ~95% | Aggregators + APIs + scrapers + alerts |
| 2. Filtering & ranking | ~90% | Rules + LLM scoring against your profile |
| 3. Resume / cover-letter tailoring | ~80% | LLM drafts, you approve |
| 4. Application submission | ~50% | Easy on some boards, hard/ToS-risky on others |
| 5. Tracking & follow-up | ~95% | Pipeline DB + reminders |
| 6. Interview prep | ~70% | Company research + Q generation |
| 7. Networking outreach | ~60% | Drafted messages, human sends |

Net: a realistic **70–85% reduction in manual effort** is achievable. Full 100% is
neither legal nor wise — you want a human gate before anything is sent.

## Architecture sketch

```
                 ┌─────────────────┐
                 │  Source adapters │  Greenhouse, Lever, LinkedIn,
                 │  (fetch postings)│  Indeed, company boards, RSS
                 └────────┬─────────┘
                          │  raw postings
                 ┌────────▼─────────┐
                 │   Normalizer     │  dedupe, parse, store
                 └────────┬─────────┘
                          │
                 ┌────────▼─────────┐
                 │  Scorer / Ranker │  LLM + rules vs. your profile
                 └────────┬─────────┘
                          │  ranked, scored jobs
                 ┌────────▼─────────┐
                 │   Review queue   │  ◄── YOU approve / reject
                 └────────┬─────────┘
                          │  approved
        ┌─────────────────┼──────────────────┐
        ▼                 ▼                  ▼
 ┌────────────┐   ┌──────────────┐   ┌──────────────┐
 │ Tailor docs│   │ Auto-apply   │   │ Track + nudge│
 │ (resume/CL)│   │ (where safe) │   │ (pipeline DB)│
 └────────────┘   └──────────────┘   └──────────────┘
```

## Open questions (let's discuss)

See [DISCUSSION.md](./DISCUSSION.md) for the decisions we need to make before building.
