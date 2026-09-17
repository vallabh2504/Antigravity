"""Where this installation keeps its data, and how to read it.

Layout of a checkout::

    profile/          your private material (gitignored, except *.example.* files)
      config.yml        search, scoring and writer settings
      companies.yml     company watchlist
      master_resume.yml the facts about you that applications may use
      profile.md        optional narrative facts
      writer_answers.md your answers to the planner's open questions
      writer_examples/  optional: content.json files of applications you liked
    output/jobs.db    the job database
    reports/          daily Markdown digests
    Applications/     one folder per prepared application

``JOBAUTO_HOME`` overrides the project root and ``JOBAUTO_PROFILE_DIR`` the
profile folder.  Both are read on every access, so ``jobauto --home`` works.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

PACKAGE_DIR = Path(__file__).resolve().parent
CHECKOUT_DIR = PACKAGE_DIR.parent.parent  # <root>/src/jobauto -> <root>


def _is_root(path: Path) -> bool:
    return (path / "profile").is_dir() and (path / "skills").is_dir()


def project_root() -> Path:
    override = os.environ.get("JOBAUTO_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    cwd = Path.cwd()
    if _is_root(cwd):
        return cwd
    if _is_root(CHECKOUT_DIR):
        return CHECKOUT_DIR
    return cwd


def profile_dir() -> Path:
    override = os.environ.get("JOBAUTO_PROFILE_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return project_root() / "profile"


def __getattr__(name: str) -> Path:
    # Computed on access so an override set after import still applies.
    if name == "REPO_DIR":
        return project_root()
    if name == "SKILL_DIR":
        return profile_dir()
    raise AttributeError(name)


def skills_dir() -> Path:
    for base in (project_root(), CHECKOUT_DIR):
        if (base / "skills").is_dir():
            return base / "skills"
    return project_root() / "skills"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def example_path(filename: str) -> Path:
    """The neutral template shipped next to the private file of the same name."""
    stem, dot, ext = filename.rpartition(".")
    example = f"{stem}.example.{ext}" if dot else f"{filename}.example"
    for base in (profile_dir(), CHECKOUT_DIR / "profile"):
        if (base / example).is_file():
            return base / example
    return CHECKOUT_DIR / "profile" / example


def load_config() -> dict[str, Any]:
    path = profile_dir() / "config.yml"
    cfg = _load_yaml(path) if path.is_file() else _load_yaml(example_path("config.yml"))
    override = os.environ.get("JOBAUTO_MAX_AGE_DAYS", "").strip()
    if override.isdigit():
        cfg["max_age_days"] = int(override)
    return cfg


def load_companies() -> list[dict[str, Any]]:
    path = profile_dir() / "companies.yml"
    data = _load_yaml(path) if path.is_file() else _load_yaml(example_path("companies.yml"))
    return data.get("companies", []) or []


def load_profile() -> str:
    path = profile_dir() / "profile.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def load_secrets() -> dict[str, Any]:
    return _load_yaml(profile_dir() / "secrets.yml")


def output_dir() -> Path:
    d = project_root() / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def reports_dir() -> Path:
    d = project_root() / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


def applications_dir() -> Path:
    return project_root() / "Applications"


def db_path() -> Path:
    return output_dir() / "jobs.db"
