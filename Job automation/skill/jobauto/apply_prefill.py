"""Stage 6: pre-fill application forms up to (never past) the submit button.

Two paths:
  * PREFERRED — OpenClaw's built-in browser tool. The agent reads `cli to-prefill`,
    opens each application URL, fills fields from the applicant secrets + tailored
    docs, screenshots the filled form, and STOPS. SKILL.md contains the exact agent
    instructions. No code here drives OpenClaw's browser — the agent does.
  * FALLBACK — Playwright (this module), for hosts without OpenClaw's browser.

Hard rule: this NEVER clicks submit, never solves CAPTCHAs, never touches auth walls.
"""
from __future__ import annotations

from typing import Any

from .db import DB


def build_prefill_tasks(db: DB, applicant: dict[str, Any]) -> dict[str, Any]:
    """Emit docs_ready jobs for the agent's browser to pre-fill."""
    jobs = []
    for job in db.by_state("docs_ready"):
        jobs.append({
            "id": job["id"],
            "company": job["company"],
            "title": job["title"],
            "apply_url": job["url"],
            "resume_path": f"output/{job['id']}/resume.md",
            "cover_letter_path": f"output/{job['id']}/cover_letter.md",
        })
    return {
        "instructions": (
            "For each job: open apply_url in the browser. Fill name, email, phone, "
            "LinkedIn/GitHub, location, and answer common free-text questions using the "
            "applicant profile + the tailored cover letter. Upload resume_pdf_path if a "
            "file field exists. Take a screenshot of the FILLED form. DO NOT click submit. "
            "Then call `cli set-state prefilled <id>`. If the portal needs login/CAPTCHA "
            "or is a custom flow you can't complete, mark it `manual` in your reply and skip."
        ),
        "applicant": applicant,
        "jobs": jobs,
    }


# --- Playwright fallback (only used off-OpenClaw) ---------------------------
def prefill_with_playwright(task_job: dict, applicant: dict) -> str:
    """Best-effort generic form fill. Returns 'prefilled' | 'manual' | 'error'."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "manual"  # playwright not installed; let the human do it
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(task_job["apply_url"], timeout=30000)
            field_map = {
                "first": applicant.get("full_name", "").split(" ")[0],
                "last": applicant.get("full_name", "").split(" ")[-1],
                "name": applicant.get("full_name", ""),
                "email": applicant.get("email", ""),
                "phone": applicant.get("phone", ""),
                "linkedin": applicant.get("linkedin", ""),
            }
            for key, val in field_map.items():
                if not val:
                    continue
                for sel in (f"input[name*='{key}' i]", f"input[id*='{key}' i]"):
                    try:
                        loc = page.locator(sel).first
                        if loc.count():
                            loc.fill(val)
                            break
                    except Exception:
                        continue
            page.screenshot(path=f"output/{task_job['id']}/prefill.png", full_page=True)
            browser.close()
            return "prefilled"  # NOTE: submit intentionally never clicked
    except Exception:
        return "manual"
