# job-automation skill

An OpenClaw skill that runs the full 7-stage fuel-cell job search from `../profile.md`.
The Python package `jobauto` is deterministic plumbing; the **agent** (OpenClaw, or
Claude on-demand) does portal fetching and LLM scoring/tailoring. See **SKILL.md** for
the agent runbook.

## Run it manually right now (no cron, agent-triggered)
From this directory:
```bash
pip install -r requirements.txt

# 1-2 discover  (direct fetch where network allows)
python -m jobauto fetch
#   ...or agent-fetch backend:
python -m jobauto manifest          # the requests to make
#   <agent fetches them -> raw.json>
python -m jobauto ingest raw.json

# 3 score
python -m jobauto to-score          # -> output/to_score.json
#   <agent scores -> scores.json>
python -m jobauto apply-scores scores.json

# 4 digest + human gate
python -m jobauto report            # -> ../reports/YYYY-MM-DD.md
python -m jobauto approve <id> <id>

# 5 tailor (curated per job)
python -m jobauto to-tailor         # -> output/to_tailor.json (full JD)
#   <agent drafts -> docs.json>
python -m jobauto apply-tailor docs.json   # -> output/<id>/resume.md, cover_letter.md

# 6 pre-fill (stops at submit)
python -m jobauto to-prefill
#   <agent browser fills form, screenshots, never submits>
python -m jobauto set-state prefilled <id>

# track
python -m jobauto stats
python -m jobauto set-state applied <id>
```

## Hand off to OpenClaw
```bash
bash install.sh         # symlinks this into ~/.openclaw/workspace/skills/
```
Then in OpenClaw: edit `secrets.yml` + `master_resume.yml`, say **"run the job search"**,
and finally add a morning **cron job** (SKILL.md > Cron).

## Layout
```
jobauto/        package: models, db, sources/, normalize, score, tailor, apply_prefill, digest, cli
config.yml      keywords, locations, delivery
companies.yml   portals to watch (Greenhouse/Lever/Ashby/SmartRecruiters/Workday/custom)
secrets.example.yml / master_resume.example.yml   templates (copy to .yml, gitignored)
sample_raw.json demo fixture used to validate the pipeline in a sandbox
SKILL.md        the OpenClaw agent runbook
install.sh      symlink + deps + seed config
```

## Notes
- **Pre-fill only — never auto-submits.** A human clicks send.
- **No LinkedIn/Indeed scraping** — ingest their alert emails via Gmail instead.
- `../output/` and `secrets.yml`/`master_resume.yml` are gitignored; `../reports/` is committed.
- `companies.yml` portal tokens are best-guess starting points — verify on first live run.
