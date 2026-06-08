"""Stage 0: SOURCE discovery — find new employers automatically.

The problem: a hand-typed company list never covers Europe. Solution: have the
agent run web search-operator ("dork") queries that surface companies hosting a
public ATS board with fuel-cell/hydrogen roles, then auto-append them to
companies.yml. Re-run periodically to keep the universe fresh.

Flow (agent backend):
  1. `cli discover-sources`  -> output/discover_queries.json  (the searches to run)
  2. The agent runs each query with web/browser tools, reads result URLs, and maps
     each hit to {name, portal, token} using url_to_company() below.
  3. The agent writes new_companies.json and calls `cli add-companies new_companies.json`.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

# ATS board URL signatures -> (portal, how to extract the token)
_ATS_PATTERNS = [
    ("greenhouse",      re.compile(r"boards\.greenhouse\.io/([^/?#]+)")),
    ("greenhouse",      re.compile(r"job-boards\.greenhouse\.io/([^/?#]+)")),
    ("lever",           re.compile(r"jobs\.lever\.co/([^/?#]+)")),
    ("ashby",           re.compile(r"jobs\.ashbyhq\.com/([^/?#]+)")),
    ("smartrecruiters", re.compile(r"jobs\.smartrecruiters\.com/([^/?#]+)")),
    ("personio",        re.compile(r"([a-z0-9-]+)\.jobs\.personio\.(?:de|com)")),
    ("recruitee",       re.compile(r"([a-z0-9-]+)\.recruitee\.com")),
    ("teamtailor",      re.compile(r"([a-z0-9-]+)\.teamtailor\.com")),
    ("workday",         re.compile(r"([a-z0-9-]+)\.[a-z0-9]+\.myworkdayjobs\.com")),
]

# Keyword sets and the domain we want, combined into dorks per ATS host.
_ATS_HOSTS = {
    "greenhouse": "boards.greenhouse.io",
    "lever": "jobs.lever.co",
    "ashby": "jobs.ashbyhq.com",
    "smartrecruiters": "jobs.smartrecruiters.com",
    "personio": "jobs.personio.de",
    "recruitee": "recruitee.com",
    "teamtailor": "teamtailor.com",
    "workday": "myworkdayjobs.com",
}


def build_discovery_queries(keywords: list[str], locales: list[str]) -> dict[str, Any]:
    terms = keywords or ["fuel cell", "hydrogen", "Brennstoffzelle", "Wasserstoff"]
    queries = []
    # 1) ATS-scoped dorks (find companies hosting matching roles on each ATS)
    for portal, host in _ATS_HOSTS.items():
        for term in terms:
            queries.append({"kind": "ats", "portal": portal,
                            "query": f'site:{host} "{term}"'})
    # 2) Plain discovery for company universe / directories
    for term in terms:
        for loc in (locales or ["Europe", "Germany"]):
            queries.append({"kind": "directory",
                            "query": f'{term} companies {loc} careers'})
        queries.append({"kind": "directory",
                        "query": f'Hydrogen Europe members {term} OR "fuel cell"'})
    return {
        "instructions": (
            "Run each query with web/browser tools. For 'ats' queries, collect result "
            "URLs and pass them to url_to_company (or map host->token yourself) to build "
            "{name, portal, token, sectors} entries — only keep employers plausibly in "
            "aviation/rail/heavy fuel-cell/hydrogen. For 'directory' queries, extract new "
            "company names + their careers URLs. Dedupe against existing companies.yml. "
            "Write the new entries to new_companies.json and run `cli add-companies`."
        ),
        "queries": queries,
    }


def url_to_company(url: str, name_hint: str = "", sectors: list[str] | None = None) -> dict | None:
    """Map an ATS board URL to a companies.yml entry."""
    for portal, pat in _ATS_PATTERNS:
        m = pat.search(url)
        if not m:
            continue
        token = m.group(1)
        if portal == "workday":
            host = urlparse(url).netloc
            # tenant|site|host needs the path; agent should refine. Best-effort:
            token = f"{m.group(1)}||{host}"
        name = name_hint or token.replace("-", " ").title()
        return {"name": name, "portal": portal, "token": token,
                "sectors": sectors or [], "careers_url": url, "auto_discovered": True}
    return None
