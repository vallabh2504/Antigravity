# Dashboard

Agent-agnostic web UI over the pipeline (`../output/jobs.db`). Browse ranked jobs,
approve/reject with a click, and read tailored docs + full JD.

## Run locally
```bash
pip install fastapi uvicorn
cd "Job automation"
uvicorn dashboard.app:app --reload --port 8000
# open http://localhost:8000
```

- `/`            review queue (scored + approved) with Approve/Reject buttons
- `/all`         every job
- `/state/<s>`   filter by pipeline state (applied, docs_ready, …)
- `/job/<id>`    full JD + tailored documents

Approvals write straight back to `jobs.db`, so the CLI and dashboard stay in sync
(`python -m jobauto next` will reflect dashboard actions).

## Deploy (optional)
Vercel/any host works for a **read-only** view (serverless filesystems are ephemeral,
so SQLite writes don't persist). For approvals, run it locally next to the DB, or point
it at a shared Postgres later. Local is the intended use.
