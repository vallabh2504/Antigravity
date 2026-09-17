"""Bundesagentur fuer Arbeit (jobboerse) source adapter, v6 search route.

Route, verified live on 2026-09-16 from this project's own virtualenv:

  list    GET  https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs
          header ``X-API-Key: jobboerse-jobsuche``            -> 200
  detail  GET  .../pc/v4/jobdetails/{base64(referenznummer)}  -> 200, or 404 once the
          posting has been withdrawn.

The previous adapter used ``/pc/v4/app/jobs``.  That route now answers **403** for
every request, which is the operator's second complaint: the tool reported the
source as blocked forever while the search API was healthy the whole time under a
different path.  A 403 is deliberately *not* diagnosed here as a single cause --
see ``describe_blocked`` -- because the API overloads it between throttling and a
route that has moved, and asserting one of those is how the previous failure
stayed invisible.

Field names on v6 are not the v4 ones.  The list rows carry ``referenznummer``,
``stellenangebotsTitel``, ``firma`` and ``stellenlokationen``; the detail document
carries ``stellenangebotsBeschreibung``, which is the full job description and
**must be decoded as UTF-8 explicitly**.  This machine's console encoding is
cp1252, and letting a client guess the charset is how an umlaut becomes U+FFFD
inside a committed fixture.

The apply URL is always constructed from the reference number as
``https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}``.  The detail document
also offers a partner redirect, but it is not used: it sends the applicant
somewhere other than the posting.
"""
from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import quote, urljoin, urlsplit

from ..models import RawPosting
from . import Recipe

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
LIST_PATH = "/pc/v6/jobs"
DETAIL_PATH = "/pc/v4/jobdetails/{token}"
API_KEY_HEADER = "X-API-Key"
API_KEY = "jobboerse-jobsuche"
APPLY_URL_TMPL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}"
PORTAL = "agg_bundesagentur"

#: Top-level keys of a healthy v6 search response, observed live 2026-09-16.
#: ``detect_drift`` fails when the live shape stops matching this exactly.
EXPECTED_TOP_LEVEL_KEYS = frozenset({"ergebnisliste", "maxErgebnisse", "page", "size", "facetten"})

#: Response headers worth quoting back to the operator when a request is refused.
DIAGNOSTIC_HEADERS = ("X-API-BLOCKED", "correlation-id")

DEFAULT_HEADERS = {
    API_KEY_HEADER: API_KEY,
    "Accept": "application/json",
}


class SourceBlocked(RuntimeError):
    """A refusal whose cause the API does not let us distinguish."""


class SchemaDrift(RuntimeError):
    """The response shape stopped matching the contract this adapter was written against."""


# --------------------------------------------------------------------------- urls


def build_list_url(query: str = "", where: str = "", radius_km: int = 50,
                   days: int | None = None, size: int = 50, page: int = 1) -> str:
    params = [f"size={int(size)}", f"page={int(page)}", "angebotsart=1", "pav=false"]
    if query:
        params.insert(0, f"was={quote(query)}")
    if where:
        params.append(f"wo={quote(where)}")
        params.append(f"umkreis={int(radius_km)}")
    if days:
        params.append(f"veroeffentlichtseit={int(days)}")
    return f"{BASE}{LIST_PATH}?" + "&".join(params)


def detail_token(reference: str) -> str:
    """The detail route addresses a posting by base64 of its reference number."""
    return base64.b64encode(reference.encode("utf-8")).decode("ascii")


def detail_url(reference: str) -> str:
    return BASE + DETAIL_PATH.format(token=detail_token(reference))


def apply_url(reference: str) -> str:
    return APPLY_URL_TMPL.format(ref=reference)


# ------------------------------------------------------------------------ parsing


def _location(row: dict) -> str:
    for loc in row.get("stellenlokationen") or []:
        adresse = (loc or {}).get("adresse") or {}
        parts = [adresse.get("ort"), adresse.get("plz")]
        text = ", ".join(str(p) for p in parts if p)
        if text:
            return text
    return ""


def _posted_at(row: dict) -> str:
    for key in ("datumErsteVeroeffentlichung", "aenderungsdatum"):
        value = row.get(key)
        if value:
            return str(value)
    window = row.get("veroeffentlichungszeitraum") or {}
    return str(window.get("von") or "")


def parse_list(recipe: Recipe, payload: Any) -> list[RawPosting]:
    """Map a v6 search response onto RawPostings.

    Only ``ergebnisliste`` / ``referenznummer`` / ``stellenangebotsTitel`` and the
    location block are read; a payload in the old shape yields nothing here and is
    caught by ``detect_drift`` rather than being silently half-parsed.
    """
    if not isinstance(payload, dict):
        return []
    out: list[RawPosting] = []
    for row in payload.get("ergebnisliste") or []:
        if not isinstance(row, dict):
            continue
        reference = str(row.get("referenznummer") or "").strip()
        if not reference:
            continue
        out.append(RawPosting(
            source=PORTAL,
            company=str(row.get("firma") or "Bundesagentur fuer Arbeit"),
            title=str(row.get("stellenangebotsTitel") or ""),
            location=_location(row),
            url=apply_url(reference),
            jd_text="",
            posted_at=_posted_at(row),
            extra={"referenznummer": reference, "needs_detail": True,
                   "sectors": recipe.sectors},
        ))
    return out


def parse_detail(detail: Any) -> str:
    """The full job description from a detail document, or ``""`` when absent."""
    if not isinstance(detail, dict):
        return ""
    return str(detail.get("stellenangebotsBeschreibung") or "")


def decode_json(response: Any) -> Any:
    """Decode a response body as UTF-8 JSON, never by charset guess.

    The API serves UTF-8 without always saying so.  ``response.text`` then falls
    back to the client's guess, and on a cp1252 host every umlaut in a German job
    description turns into U+FFFD -- permanently, once it is written to a fixture.
    """
    body = getattr(response, "content", None)
    if isinstance(body, (bytes, bytearray)):
        return json.loads(bytes(body).decode("utf-8"))
    return response.json()


def detect_drift(payload: Any) -> list[str]:
    """Differences between the response's top-level keys and the locked contract.

    Returns a list of human-readable differences; empty means no drift.  This is
    the detector AC-08 requires to be able to *fail*: it is exercised offline
    against a deliberately mutated fixture as well as against the live API.
    """
    if not isinstance(payload, dict):
        return [f"payload is {type(payload).__name__}, expected object"]
    found = set(payload.keys())
    problems = []
    for missing in sorted(EXPECTED_TOP_LEVEL_KEYS - found):
        problems.append(f"missing key '{missing}'")
    for added in sorted(found - EXPECTED_TOP_LEVEL_KEYS):
        problems.append(f"unexpected key '{added}'")
    return problems


# ----------------------------------------------------------------------- failures


def _header(headers: Any, name: str) -> str:
    if not headers:
        return ""
    try:
        value = headers.get(name)
    except AttributeError:
        return ""
    if value is None:
        # httpx headers are case-insensitive; a plain dict is not.
        for key, candidate in dict(headers).items():
            if str(key).lower() == name.lower():
                value = candidate
                break
    return "" if value is None else str(value)


def describe_blocked(status: int, headers: Any = None, url: str = "") -> str:
    """The operator-facing message for a refusal the API will not explain.

    A 403 from this API means *either* a throttle *or* a route that has moved, and
    nothing in the response distinguishes them.  The message therefore names both
    and commits to neither, and carries the two headers support would ask for.
    """
    blocked = _header(headers, "X-API-BLOCKED")
    correlation = _header(headers, "correlation-id") or _header(headers, "x-correlationid")
    return (
        f"Bundesagentur returned HTTP {status} for {url or LIST_PATH}: "
        "rate-limited or route changed - the cause is ambiguous and this tool "
        "will not guess between them. "
        f"X-API-BLOCKED={blocked or '(absent)'} correlation-id={correlation or '(absent)'}"
    )


# ------------------------------------------------------------------------ fetching


def _same_origin(a: str, b: str) -> bool:
    pa, pb = urlsplit(a), urlsplit(b)
    return (pa.scheme, pa.netloc) == (pb.scheme, pb.netloc)


def request(client: Any, url: str, headers: dict | None = None, max_redirects: int = 5) -> Any:
    """GET `url`, following redirects **without leaking the API key off-origin**.

    httpx's own ``follow_redirects`` forwards every request header, so a redirect
    to a third-party host would hand that host the credential.  The key is a
    public static one here, but the rule has to hold in code or it stops holding
    the day the key is not public.
    """
    current = url
    sent = dict(headers or DEFAULT_HEADERS)
    for _ in range(max_redirects + 1):
        # Disable automatic redirect handling so the credential can be removed
        # before a cross-origin hop. Older test doubles may not accept this
        # keyword, hence the compatibility fallback.
        try:
            response = client.get(current, headers=sent, follow_redirects=False)
        except TypeError:
            response = client.get(current, headers=sent)
        status = int(getattr(response, "status_code", 0) or 0)
        if status not in (301, 302, 303, 307, 308):
            return response
        location = _header(getattr(response, "headers", None), "location")
        if not location:
            return response
        next_url = urljoin(current, location)
        if not _same_origin(current, next_url):
            sent = {k: v for k, v in sent.items() if k.lower() != API_KEY_HEADER.lower()}
        current = next_url
    raise SourceBlocked(f"too many redirects from {url}")


def fetch(recipe: Recipe, client: Any, with_details: bool = True,
          detail_limit: int = 50) -> tuple[list[RawPosting], dict[str, int]]:
    """Fetch one page of search results, plus each posting's description.

    Details are fetched in the same pass on purpose: postings expire, and a
    description fetched days later is a 404 for a posting that was real.  A 404
    here is counted as ``expired``, not as an error -- an expired posting is a
    fact about the market, not a fault in the tool.
    """
    response = request(client, recipe.list_url, {**DEFAULT_HEADERS, **(recipe.headers or {})})
    status = int(getattr(response, "status_code", 0) or 0)
    if status in (401, 403, 429):
        raise SourceBlocked(describe_blocked(status, getattr(response, "headers", None),
                                             recipe.list_url))
    if status != 200:
        raise RuntimeError(f"Bundesagentur list returned HTTP {status} for {recipe.list_url}")

    payload = decode_json(response)
    drift = detect_drift(payload)
    if drift:
        # A partial parse would turn an upstream rename into a plausible-looking
        # empty source. Fail so the run report names the contract change.
        raise SchemaDrift("Bundesagentur v6 response drift: " + "; ".join(drift))
    postings = parse_list(recipe, payload)
    counts = {"listed": len(postings), "detailed": 0, "expired": 0, "detail_failed": 0}
    if drift:
        counts["drift"] = len(drift)

    if with_details:
        for posting in postings[:detail_limit]:
            reference = posting.extra.get("referenznummer", "")
            if not reference:
                continue
            try:
                detail_response = request(
                    client, detail_url(reference),
                    {**DEFAULT_HEADERS, **(recipe.headers or {})})
                detail_status = int(getattr(detail_response, "status_code", 0) or 0)
                if detail_status == 404:
                    counts["expired"] += 1
                    posting.extra["detail_status"] = "expired"
                    continue
                if detail_status == 403:
                    # As with search, this status is overloaded between throttling
                    # and a moved route. Preserve the posting, but expose the
                    # ambiguity and the gateway diagnostics on the row.
                    counts["detail_failed"] += 1
                    posting.extra["detail_status"] = "ambiguous_403"
                    posting.extra["detail_error"] = describe_blocked(
                        detail_status, getattr(detail_response, "headers", None),
                        detail_url(reference))
                    continue
                if detail_status != 200:
                    counts["detail_failed"] += 1
                    posting.extra["detail_status"] = f"http_{detail_status}"
                    continue
                posting.jd_text = parse_detail(decode_json(detail_response))
                posting.extra["detail_status"] = "ok"
                posting.extra["needs_detail"] = False
                counts["detailed"] += 1
            except Exception as exc:  # one bad detail never kills the page
                counts["detail_failed"] += 1
                posting.extra["detail_status"] = f"{type(exc).__name__}"
    return postings, counts
