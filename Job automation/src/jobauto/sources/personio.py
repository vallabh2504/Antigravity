"""Personio public XML feed source adapter.

Queries the Personio public XML endpoint:
  GET https://{token}.jobs.personio.de/xml

The feed is XML and is parsed **as XML** with ``xml.etree.ElementTree``.  It used
to be parsed with BeautifulSoup, which needs ``lxml`` for its ``"xml"`` feature
and silently fell back to ``html.parser`` when ``lxml`` was absent.  That parser
lowercases tag names, so ``createdAt``, ``employmentType`` and ``jobDescriptions``
never matched and every posting lost its date and employment type without a
single error.  See ``jobauto.sources.xmlutil`` for the full note.

Extracts ``<id>``, ``<name>`` (title), ``<jobDescriptions>``, ``<office>`` /
``<department>`` (location), ``<employmentType>``, ``<createdAt>``, and
constructs a direct application URL:
  https://{token}.jobs.personio.de/job/{id}?language=en
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from ..models import RawPosting
from ..normalize import strip_html
from . import Recipe
from .xmlutil import child, child_text, iter_named, parse_xml

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/xml,text/xml,*/*",
}

#: Feed fields whose absence means the adapter is reading a feed it does not
#: understand.  ``parse_personio`` reports them instead of emitting blanks.
DATED_FIELD = "createdAt"


def extract_token_from_url(url: str) -> str:
    """Extract the Personio subdomain/token from an XML feed URL."""
    try:
        host = urlsplit(url).netloc
        if ".jobs.personio." in host:
            return host.split(".jobs.personio.")[0]
    except Exception:
        pass
    return ""


def _job_descriptions(position) -> str:
    container = child(position, "jobDescriptions")
    if container is None:
        return ""
    parts: list[str] = []
    for jd in iter_named(container, "jobDescription"):
        if jd is container:
            continue
        sec_name = child_text(jd, "name")
        sec_val = strip_html(child_text(jd, "value"))
        if sec_name and sec_val:
            parts.append(f"{sec_name}\n{sec_val}")
        elif sec_val:
            parts.append(sec_val)
    return "\n\n".join(parts)


def parse_personio(recipe: Recipe, xml_content: str) -> list[RawPosting]:
    """Parse a Personio XML feed into RawPosting objects.

    Raises ``ValueError`` when the payload is not parseable XML: a feed that has
    become an HTML error page must surface as a source failure, never as an empty
    but "successful" result.
    """
    src = f"personio:{recipe.company}"
    out: list[RawPosting] = []
    if not xml_content or not isinstance(xml_content, str):
        return out

    root = parse_xml(xml_content)
    if root is None:
        raise ValueError(
            f"personio feed for {recipe.company} is not valid XML "
            f"({xml_content[:120]!r})"
        )

    token = extract_token_from_url(recipe.list_url) or getattr(recipe, "token", "")
    subdomain = token or recipe.company.lower().replace(" ", "-")

    for position in iter_named(root, "position"):
        job_id = child_text(position, "id")
        if not job_id:
            continue
        office = child_text(position, "office")
        dept = child_text(position, "department")
        out.append(RawPosting(
            source=src,
            company=recipe.company,
            title=child_text(position, "name"),
            location=", ".join(filter(None, [office, dept])),
            url=f"https://{subdomain}.jobs.personio.de/job/{job_id}?language=en",
            jd_text=_job_descriptions(position),
            posted_at=child_text(position, DATED_FIELD),
            extra={
                "sectors": recipe.sectors,
                "id": job_id,
                "employmentType": child_text(position, "employmentType"),
                "seniority": child_text(position, "seniority"),
                "schedule": child_text(position, "schedule"),
            },
        ))
    return out


def fetch_personio(recipe: Recipe, client: Any = None) -> list[RawPosting]:
    """Fetch and parse the Personio public XML feed."""
    import httpx

    close_client = False
    if client is None:
        client = httpx.Client(timeout=20, follow_redirects=True, headers=DEFAULT_HEADERS)
        close_client = True

    try:
        req_headers = {**DEFAULT_HEADERS, **(recipe.headers or {})}
        resp = client.get(recipe.list_url, headers=req_headers)
        resp.raise_for_status()
        return parse_personio(recipe, _decode(resp))
    finally:
        if close_client:
            client.close()


def _decode(resp: Any) -> str:
    """Decode the response body as UTF-8.

    Personio declares ``encoding="utf-8"`` in the XML prologue, but a response
    without a charset in its ``Content-Type`` makes httpx guess -- and on a
    cp1252 machine a guess turns every umlaut into mojibake inside a fixture.
    """
    body = getattr(resp, "content", None)
    if isinstance(body, (bytes, bytearray)):
        return bytes(body).decode("utf-8", errors="replace")
    return resp.text
