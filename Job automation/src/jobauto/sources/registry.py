"""What each shipped source is, what it costs, and whether it may be reused.

Two facts belong to a source and not to a user's configuration, so they live in
code and are validated on every run:

``commercial_use``
    ``permitted`` / ``prohibited`` / ``unclear``.  ``unclear`` is a real answer
    and is used where the terms do not say; guessing ``permitted`` because it is
    convenient is how a tool ships a licence violation.
``terms_url``
    Where that judgement came from, so a reader can check it rather than trust
    it.

This project is MIT-licensed and takes no revenue, so the gating is not about
protecting a sale.  It is about not silently doing something a buyer would be
liable for, and about telling the operator's own agent how to obtain a free key
for the sources that need one, rather than failing with "AUTH 403" forever.

A source marked ``prohibited`` is inert: ``enabled`` is forced to false no matter
what the configuration says.
"""
from __future__ import annotations

from dataclasses import dataclass, field

PERMITTED = "permitted"
PROHIBITED = "prohibited"
UNCLEAR = "unclear"
COMMERCIAL_USE_VALUES = (PERMITTED, PROHIBITED, UNCLEAR)


@dataclass(frozen=True)
class SourceInfo:
    key: str
    name: str
    commercial_use: str
    terms_url: str
    #: How the operator's own agent can obtain a free credential, if one is
    #: needed.  Empty when the source needs none.
    key_instructions: str = ""
    #: Shipped default.  A source needing a credential ships disabled, because a
    #: source that cannot authenticate is a guaranteed failure on first run.
    default_enabled: bool = False
    notes: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)


REGISTRY: dict[str, SourceInfo] = {
    "arbeitnow": SourceInfo(
        key="arbeitnow",
        name="Arbeitnow job board API",
        commercial_use=PERMITTED,
        terms_url="https://www.arbeitnow.com/terms",
        default_enabled=True,
        notes="Public JSON feed, no credential. Germany-heavy coverage.",
        tags=("aggregator", "no-key"),
    ),
    "bundesagentur": SourceInfo(
        key="bundesagentur",
        name="Bundesagentur fuer Arbeit - jobboerse API",
        commercial_use=UNCLEAR,
        terms_url="https://www.arbeitsagentur.de/datenschutz-impressum/nutzungsbedingungen",
        default_enabled=True,
        notes=(
            "Public static API key, no signup. The published terms cover use of the "
            "portal, not redistribution of the API's results, so commercial reuse is "
            "recorded as unclear rather than assumed."
        ),
        tags=("aggregator", "no-key", "germany"),
    ),
    "euraxess": SourceInfo(
        key="euraxess",
        name="EURAXESS research positions",
        commercial_use=UNCLEAR,
        terms_url="https://euraxess.ec.europa.eu/legal-notice",
        default_enabled=False,
        notes=(
            "Optional server-rendered HTML search parser; there is no supported JSON "
            "API. Client-rendered responses may yield zero and are reported as such."
        ),
        tags=("aggregator", "html"),
    ),
    "adzuna": SourceInfo(
        key="adzuna",
        name="Adzuna search API",
        commercial_use=PROHIBITED,
        terms_url="https://developer.adzuna.com/docs/terms",
        default_enabled=False,
        key_instructions=(
            "Register a free app_id/app_key at https://developer.adzuna.com/ and put "
            "them in profile/secrets.yml under `adzuna:`."
        ),
        notes=(
            "The free tier permits caching results for at most 14 day(s) and at most "
            "2500 calls per month, and forbids redistribution. Ships disabled and "
            "inert; enabling it is the operator's decision about their own terms."
        ),
        tags=("aggregator", "needs-key"),
    ),
    "jsearch": SourceInfo(
        key="jsearch",
        name="JSearch (RapidAPI)",
        commercial_use=UNCLEAR,
        terms_url="https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch",
        default_enabled=False,
        key_instructions=(
            "Obtain a free RapidAPI key at https://rapidapi.com/ and set it as "
            "RAPIDAPI_KEY, or as `rapidapi_key` in profile/secrets.yml."
        ),
        notes="Superseded by the JobSpy path where JobSpy can run. Ships disabled.",
        tags=("aggregator", "needs-key"),
    ),
    "jobspy": SourceInfo(
        key="jobspy",
        name="python-jobspy (Indeed / Google / LinkedIn / Glassdoor scraper)",
        commercial_use=UNCLEAR,
        terms_url="https://github.com/speedyapply/JobSpy#readme",
        default_enabled=True,
        notes=(
            "Scrapes boards whose own terms restrict automated access; linkedin and "
            "glassdoor ship disabled for that reason. Requires Python 3.12 or older: "
            "python-jobspy pins numpy==1.26.3, which has no wheel for 3.13."
        ),
        tags=("scraper", "no-key"),
    ),
    # Public ATS boards are not one contractual service: each board owner may
    # publish additional restrictions. Keep the posture explicit rather than
    # silently treating every public endpoint as permitted.
    "greenhouse": SourceInfo(
        key="greenhouse", name="Greenhouse public job board API",
        commercial_use=PERMITTED, terms_url="https://www.greenhouse.com/legal/privacy-policy",
        default_enabled=True, tags=("ats", "no-key")),
    "lever": SourceInfo(
        key="lever", name="Lever public postings API",
        commercial_use=PERMITTED, terms_url="https://www.lever.co/terms-of-use",
        default_enabled=True, tags=("ats", "no-key")),
    "ashby": SourceInfo(
        key="ashby", name="Ashby public job board API",
        commercial_use=UNCLEAR, terms_url="https://www.ashbyhq.com/terms",
        default_enabled=True, tags=("ats", "no-key")),
    "smartrecruiters": SourceInfo(
        key="smartrecruiters", name="SmartRecruiters public postings API",
        commercial_use=PERMITTED, terms_url="https://www.smartrecruiters.com/legal/terms-of-use/",
        default_enabled=True, tags=("ats", "no-key")),
    "workday": SourceInfo(
        key="workday", name="Workday public career board API",
        commercial_use=UNCLEAR, terms_url="https://www.workday.com/en-us/legal.html",
        default_enabled=True, tags=("ats", "no-key")),
    "personio": SourceInfo(
        key="personio", name="Personio public XML job feed",
        commercial_use=UNCLEAR, terms_url="https://www.personio.com/legal-notice/",
        default_enabled=True, tags=("ats", "no-key")),
    "custom": SourceInfo(
        key="custom", name="Company careers page (schema.org/microdata)",
        commercial_use=UNCLEAR, terms_url="https://www.rfc-editor.org/rfc/rfc9309",
        default_enabled=True, tags=("html", "per-company-terms")),
}

#: JobSpy back-ends that are off in the shipped default because the site's own
#: terms prohibit automated access.  Turning one on is the operator accepting
#: that risk explicitly, which is why the reason travels with the flag.
JOBSPY_OPT_IN_SITES = {
    "linkedin": (
        "Disabled by default. LinkedIn's User Agreement prohibits automated "
        "scraping; enabling this means the operator accepts the ToS risk."
    ),
    "glassdoor": (
        "Disabled by default. Glassdoor's terms prohibit automated collection, and "
        "it 403s datacenter IPs on most runs; enabling this means the operator "
        "accepts the ToS risk."
    ),
}

JOBSPY_DEFAULT_SITES = ("indeed", "google")


def validate_registry(registry: dict[str, SourceInfo] | None = None) -> list[str]:
    """Schema problems in the shipped source registry; empty means valid."""
    entries = registry if registry is not None else REGISTRY
    problems: list[str] = []
    for key, info in entries.items():
        if info.commercial_use not in COMMERCIAL_USE_VALUES:
            problems.append(
                f"{key}: commercial_use {info.commercial_use!r} not in {COMMERCIAL_USE_VALUES}")
        if not info.terms_url.startswith("http"):
            problems.append(f"{key}: terms_url is not a URL ({info.terms_url!r})")
        if info.commercial_use == PROHIBITED and info.default_enabled:
            problems.append(f"{key}: commercial_use is prohibited but it ships enabled")
        if "needs-key" in info.tags and not info.key_instructions:
            problems.append(f"{key}: needs a credential but gives no way to obtain one")
    return problems


def is_enabled(key: str, cfg_entry: dict | None) -> bool:
    """Whether a source runs, with the prohibited-is-inert rule applied.

    A configuration cannot enable a source whose terms forbid this use. That is
    the whole point of recording the terms next to the adapter.
    """
    info = REGISTRY.get(key)
    if info is not None and info.commercial_use == PROHIBITED:
        return False
    if cfg_entry is None:
        return bool(info.default_enabled) if info else False
    return bool(cfg_entry.get("enabled", info.default_enabled if info else False))


def jobspy_sites(configured: list[str] | None,
                 accepted_tos_risk: list[str] | None = None) -> tuple[list[str], list[str]]:
    """Split configured JobSpy back-ends into (allowed, refused).

    A site in ``JOBSPY_OPT_IN_SITES`` runs only when the operator has named it in
    ``jobspy.accept_tos_risk``.  Listing it under ``sites`` alone is not enough:
    accepting a terms-of-service risk has to be a separate, deliberate act, or it
    happens by copy-paste.
    """
    sites = list(JOBSPY_DEFAULT_SITES) if configured is None else configured
    accepted = {str(s).strip().lower() for s in (accepted_tos_risk or [])}
    allowed: list[str] = []
    refused: list[str] = []
    for site in sites:
        name = str(site).strip().lower()
        if not name:
            continue
        if name in JOBSPY_OPT_IN_SITES and name not in accepted:
            refused.append(name)
            continue
        if name not in allowed:
            allowed.append(name)
    return allowed, refused


def describe(key: str) -> dict:
    info = REGISTRY.get(key)
    if info is None:
        return {"source": key, "commercial_use": UNCLEAR, "terms_url": ""}
    return {
        "source": info.key,
        "name": info.name,
        "commercial_use": info.commercial_use,
        "terms_url": info.terms_url,
        "key_instructions": info.key_instructions,
        "default_enabled": info.default_enabled,
        "notes": info.notes,
    }
