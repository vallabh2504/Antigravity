"""Stage 7 delivery: build the daily Markdown report + a short digest string."""
from __future__ import annotations

from datetime import date

from .config import reports_dir
from .db import DB


def _fmt_job(j: dict, idx: int) -> str:
    sj = j.get("score_json") or {}
    tags = []
    if sj.get("sector"):
        tags.append(sj["sector"])
    if sj.get("is_phd"):
        tags.append("PhD")
    if sj.get("german_required"):
        tags.append(f"DE:{sj['german_required']}")
    if sj.get("tier"):
        tags.append(f"tier {sj['tier']}")
    from .util import age_days
    a = age_days(j.get("posted_at", ""))
    if a is not None:
        tags.append("today" if a <= 0 else f"{a}d ago")
    else:
        tags.append("date?")
    if sj.get("link_state") == "gone":
        tags.append("⚠ link dead")
    elif sj.get("link_state") == "unverified":
        tags.append("link unverified")
    tagstr = "  ·  ".join(tags)
    reasons = sj.get("reasons") or []
    lines = [
        f"### {idx}. {j['title']} — {j['company']}  ({j.get('score','?')}/100)",
        f"*{j['location'] or 'location n/a'}*  ·  {tagstr}" if tagstr else f"*{j['location'] or 'location n/a'}*",
        "",
    ]
    for r in reasons[:4]:
        lines.append(f"- {r}")
    if j.get("url"):
        lines.append(f"\n[Open posting]({j['url']})  ·  `id: {j['id']}`  ·  state: **{j['state']}**")
    return "\n".join(lines)


def build_report(db: DB, top_n: int = 15, min_score: int = 50,
                 max_age_days: int | None = None) -> tuple[str, str]:
    """Return (report_path, markdown). Writes reports/YYYY-MM-DD.md.

    If max_age_days is set, only postings posted within that window (or with an unknown
    date, which are flagged) are shown — the "last N days" requirement.
    """
    from .util import age_days
    today = date.today().isoformat()
    scored = [j for j in db.all() if j.get("score") is not None and j["state"] not in ("rejected",)]

    def _fresh(j):
        if max_age_days is None:
            return True
        a = age_days(j.get("posted_at", ""))
        return a is None or a <= max_age_days   # keep unknown-date, but they get flagged
    scored = [j for j in scored if _fresh(j)]
    ranked = sorted(scored, key=lambda j: j.get("score") or 0, reverse=True)
    shortlist = [j for j in ranked if (j.get("score") or 0) >= min_score][:top_n]
    counts = db.counts()

    md = [f"# Job digest — {today}", ""]
    md.append("**Pipeline:** " + "  ·  ".join(f"{k}: {v}" for k, v in sorted(counts.items())) or "empty")
    md.append("")
    md.append(f"## Top matches (score ≥ {min_score})")
    md.append("")
    if not shortlist:
        md.append("_No new matches above threshold today._")
    for i, j in enumerate(shortlist, 1):
        md.append(_fmt_job(j, i))
        md.append("")

    # follow-ups
    applied = db.by_state("applied")
    if applied:
        md.append("## Awaiting follow-up")
        for j in applied:
            md.append(f"- {j['title']} — {j['company']} (applied {j.get('applied_at','')[:10]})")
        md.append("")

    md.append("---")
    md.append("_Reply with `approve <id> <id>` or `reject <id>` to move jobs through the pipeline._")
    text = "\n".join(md)

    path = reports_dir() / f"{today}.md"
    path.write_text(text, encoding="utf-8")

    digest = f"Job digest {today}: {len(shortlist)} top matches (≥{min_score}). "
    if shortlist:
        digest += "Highlights: " + "; ".join(
            f"{j['company']} {j['title']} ({j['score']})" for j in shortlist[:3])
    return str(path), text
