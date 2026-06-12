"""Load config.yml, companies.yml, profile.md and the master resume."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

SKILL_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = SKILL_DIR.parent  # the "Job automation" folder


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_config() -> dict[str, Any]:
    cfg = _load_yaml(SKILL_DIR / "config.yml")
    # Optional override for the freshness window (used for diagnostic runs via the
    # workflow's `max_age_days` input) so we never have to churn the "3 days" default.
    override = os.environ.get("JOBAUTO_MAX_AGE_DAYS", "").strip()
    if override.isdigit():
        cfg["max_age_days"] = int(override)
    return cfg


def load_companies() -> list[dict[str, Any]]:
    data = _load_yaml(SKILL_DIR / "companies.yml")
    return data.get("companies", [])


def load_profile() -> str:
    """The candidate profile, fed to the LLM for scoring & tailoring."""
    p = REPO_DIR / "profile.md"
    return p.read_text(encoding="utf-8") if p.exists() else ""


def load_secrets() -> dict[str, Any]:
    for name in ("secrets.yml", "secrets.example.yml"):
        p = SKILL_DIR / name
        if p.exists():
            return _load_yaml(p)
    return {}


def load_master_resume() -> str:
    for name in ("master_resume.yml", "master_resume.example.yml"):
        p = SKILL_DIR / name
        if p.exists():
            return p.read_text(encoding="utf-8")
    return ""


def output_dir() -> Path:
    d = REPO_DIR / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def reports_dir() -> Path:
    d = REPO_DIR / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def applications_dir() -> Path:
    """Committed, editable application packets (resume.md / cover_letter.md + rendered HTML)."""
    d = REPO_DIR / "applications"
    d.mkdir(parents=True, exist_ok=True)
    return d


def db_path() -> Path:
    return REPO_DIR / "output" / "jobs.db"
