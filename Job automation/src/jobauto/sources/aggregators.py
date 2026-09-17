"""Aggregator sources - one query reaches many employers at once.

Each of these returns a posting DATE and a canonical APPLY LINK, which is what
makes a freshness window and a trustworthy link possible at all.  What each
source is, whether its terms permit this use, and how to obtain a credential for
it live in :mod:`jobauto.sources.registry`, next to the adapter rather than in a
comment somewhere.

Every search term here comes from the operator's own profile.  Nothing in this
module hard-codes an industry, a country or a candidate: a tool that only finds
one person's kind of job in one country is not a tool, it is that person's
script.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import quote
from urllib.parse import urljoin

from ..models import RawPosting
from ..normalize import strip_html
from . import Recipe
from . import bundesagentur as ba
from .registry import REGISTRY, is_enabled


def _terms(key: str) -> dict:
    info = REGISTRY.get(key)
    if info is None:
        return {}
    return {"commercial_use": info.commercial_use, "terms_url": info.terms_url}


def _query(entry: dict, cfg: dict[str, Any]) -> str:
    """The search term for one aggregator: its own, else the profile's keywords."""
    own = str(entry.get("query", "") or "").strip()
    if own:
        return own
    keywords = [str(k) for k in cfg.get("include_keywords", []) if str(k).strip()]
    return " ".join(keywords[:4])


def _profile_country(cfg: dict[str, Any]) -> str:
    value = cfg.get("search_country")
    if value:
        return str(value).strip()
    countries = cfg.get("target_countries")
    if isinstance(countries, (list, tuple)) and countries:
        return str(countries[0]).strip()
    if countries:
        return str(countries).strip()
    return ""


def _profile_location(cfg: dict[str, Any]) -> str:
    value = cfg.get("search_location")
    if value:
        return str(value).strip()
    locations = cfg.get("search_locations")
    if isinstance(locations, (list, tuple)) and locations:
        return str(locations[0]).strip()
    if locations:
        return str(locations).strip()
    return ""


def build_aggregator_recipes(cfg: dict[str, Any], secrets: dict[str, Any]) -> list[Recipe]:
    agg = cfg.get("aggregators", {}) or {}
    days = int(cfg.get("max_age_days", 3))
    where = _profile_location(cfg)
    out: list[Recipe] = []

    j = agg.get("jsearch", {}) or {}
    if is_enabled("jsearch", j):
        key = secrets.get("rapidapi_key", "") or os.environ.get("RAPIDAPI_KEY", "")
        q = quote(_query(j, cfg))
        country = j.get("country", "") or _profile_country(cfg)
        window = {1: "today", 3: "3days", 7: "week"}.get(days, "week")
        out.append(Recipe("JSearch", "agg_jsearch",
            f"https://jsearch.p.rapidapi.com/search?query={q}&date_posted={window}"
            f"&page=1&num_pages=1&country={country}",
            headers={"X-RapidAPI-Key": key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"}))

    a = agg.get("adzuna", {}) or {}
    if is_enabled("adzuna", a):
        ad = secrets.get("adzuna", {}) or {}
        country = a.get("country", "") or cfg.get("search_country", "gb")
        what = quote(_query(a, cfg))
        where_param = quote(a.get("where", where) or "")
        out.append(Recipe("Adzuna", "agg_adzuna",
            f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
            f"?app_id={ad.get('app_id','')}&app_key={ad.get('app_key','')}"
            f"&what={what}&where={where_param}&results_per_page=50&max_days_old={days}"
            f"&sort_by=date&content-type=application/json"))

    n = agg.get("arbeitnow", {}) or {}
    if is_enabled("arbeitnow", n):
        out.append(Recipe("Arbeitnow", "agg_arbeitnow",
                          "https://www.arbeitnow.com/api/job-board-api"))

    b = agg.get("bundesagentur", {}) or {}
    if is_enabled("bundesagentur", b):
        out.append(Recipe("Bundesagentur", ba.PORTAL,
            ba.build_list_url(query=_query(b, cfg),
                              where=str(b.get("where", where) or ""),
                              radius_km=int(b.get("radius_km", 50)),
                              days=days,
                              size=int(b.get("size", 50))),
            headers=dict(ba.DEFAULT_HEADERS)))

    e = agg.get("euraxess", {}) or {}
    if is_enabled("euraxess", e):
        kw = quote(_query(e, cfg))
        out.append(Recipe("EURAXESS", "agg_euraxess",
            f"https://euraxess.ec.europa.eu/jobs/search?keywords={kw}", needs_detail=True))
    return out


def parse_aggregator(recipe: Recipe, payload: Any, include_kw: list[str]) -> list[RawPosting]:
    portal = recipe.portal
    out: list[RawPosting] = []
    keywords = list(include_kw)

    def _match(text: str) -> bool:
        from ..util import contains_keyword
        return not keywords or any(contains_keyword(text, k) for k in keywords)

    try:
        if portal == "agg_jsearch":
            for j in payload.get("data", []):
                loc = ", ".join(filter(None, [j.get("job_city"), j.get("job_country")]))
                out.append(RawPosting(portal, j.get("employer_name", "JSearch"),
                    j.get("job_title", ""), loc, j.get("job_apply_link", ""),
                    strip_html(j.get("job_description", "")),
                    str(j.get("job_posted_at_datetime_utc", "")), dict(_terms("jsearch"))))
        elif portal == "agg_adzuna":
            for j in payload.get("results", []):
                out.append(RawPosting(portal, (j.get("company") or {}).get("display_name", "Adzuna"),
                    j.get("title", ""), (j.get("location") or {}).get("display_name", ""),
                    j.get("redirect_url", ""), strip_html(j.get("description", "")),
                    str(j.get("created", "")), dict(_terms("adzuna"))))
        elif portal == "agg_arbeitnow":
            for j in payload.get("data", []):
                blob = f"{j.get('title','')} {' '.join(j.get('tags',[]))} {j.get('description','')}"
                if not _match(blob):
                    continue
                out.append(RawPosting(portal, j.get("company_name", "Arbeitnow"),
                    j.get("title", ""), j.get("location", ""), j.get("url", ""),
                    strip_html(j.get("description", "")), str(j.get("created_at", "")),
                    dict(_terms("arbeitnow"))))
        elif portal == ba.PORTAL:
            rows = ba.parse_list(recipe, payload)
            for row in rows:
                row.extra.update(_terms("bundesagentur"))
            return rows
        elif portal == "agg_euraxess":
            return parse_euraxess(recipe, payload, include_kw)
    except (AttributeError, TypeError):
        pass
    return out


def parse_euraxess(recipe: Recipe, payload: Any, include_kw: list[str]) -> list[RawPosting]:
    """Parse recorded/server-rendered EURAXESS result cards.

    EURAXESS serves a normal HTML result page for some requests and a client
    rendered shell for others. The parser only emits cards with a job-shaped
    URL and title, making the latter an explicit zero-yield outcome in health.
    """
    if not isinstance(payload, str) or not payload.strip():
        return []
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(payload, "html.parser")
    out: list[RawPosting] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        href = str(link.get("href", ""))
        lowered_href = href.lower()
        if ("/jobs/" not in lowered_href and "/job/" not in lowered_href
                and "jobid=" not in lowered_href):
            continue
        url = urljoin(recipe.list_url, href)
        # The portal nests the link in several layout wrappers. Prefer the
        # nearest card-like ancestor that actually contains a heading/title so
        # a wrapper's "Details" label cannot become the posting title.
        card = None
        for ancestor in link.parents:
            if ancestor.name not in {"article", "li", "div"}:
                continue
            if ancestor.select_one("h1,h2,h3,h4,.title,.job-title"):
                card = ancestor
                break
        card = card or link.parent
        title_node = card.select_one("h1,h2,h3,h4,.title,.job-title") if card else None
        title = " ".join((title_node or link).get_text(" ", strip=True).split())
        if not title or url in seen:
            continue
        text = " ".join(card.get_text(" ", strip=True).split()) if card else title
        if include_kw:
            from ..util import contains_keyword
            if not any(contains_keyword(text, key) for key in include_kw):
                continue
        company_node = card.select_one(".organisation,.organization,.company") if card else None
        location_node = card.select_one(".location,.job-location") if card else None
        date_node = card.select_one("time,[datetime],.date,.posted") if card else None
        posted_at = ""
        if date_node:
            posted_at = str(date_node.get("datetime", "") or
                            date_node.get_text(" ", strip=True))
        seen.add(url)
        out.append(RawPosting(
            recipe.portal, company_node.get_text(" ", strip=True) if company_node else "EURAXESS",
            title, location_node.get_text(" ", strip=True) if location_node else "",
            url, text, posted_at,
            {**_terms("euraxess"), "structured_data": "euraxess_html"}))
    return out
