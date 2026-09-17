"""Extract schema.org ``JobPosting`` records out of a careers page's HTML.

This is the generic handler for companies whose ``portal`` is ``custom``.  Before
it existed, ``fetch_recipe`` returned ``[]`` for every one of them without a word,
so 58 of the 66 configured companies were dead *by construction* and the run
report called them ``agent_only`` -- a number no report ever questioned.

Two encodings of the same vocabulary are read, because real careers pages use
both and a JSON-LD-only extractor silently misses half of them:

* **JSON-LD** -- ``<script type="application/ld+json">`` carrying a ``JobPosting``,
  possibly nested inside ``@graph`` or an ``ItemList``.  Observed on
  arbeitnow.com and arbeitsagentur.de.
* **Microdata** -- ``itemscope itemtype=".../JobPosting"`` with ``itemprop``
  attributes.  Observed on jobs.smartrecruiters.com, which emits no JSON-LD at
  all.

Measured limit, recorded here rather than discovered later by a buyer: on
2026-09-16 all 58 configured ``custom`` careers pages were fetched and **none**
carried a JobPosting in its server-rendered HTML -- they are client-rendered
search applications.  This extractor therefore works on *posting* pages and on
server-rendered boards, not on a JavaScript careers search page.  For those the
tool still emits an agent-fetch manifest, and ``docs/source-policy.md`` says so.
"""
from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

from ..models import RawPosting
from ..normalize import strip_html

JOB_POSTING_TYPE = "jobposting"

_LD_BLOCK = re.compile(
    r"<script[^>]*type\s*=\s*['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_SELF_CLOSING = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                 "meta", "param", "source", "track", "wbr"}


# ------------------------------------------------------------------- JSON-LD


def _iter_ld_objects(node: Any):
    """Every dict inside a decoded JSON-LD document, including @graph members."""
    if isinstance(node, list):
        for item in node:
            yield from _iter_ld_objects(item)
    elif isinstance(node, dict):
        yield node
        for key in ("@graph", "itemListElement", "item", "mainEntity"):
            if key in node:
                yield from _iter_ld_objects(node[key])


def _is_job_posting(obj: dict) -> bool:
    types = obj.get("@type")
    if isinstance(types, str):
        types = [types]
    return any(str(t).strip().lower() == JOB_POSTING_TYPE for t in (types or []))


def extract_jsonld_postings(html: str) -> list[dict]:
    """Every JSON-LD ``JobPosting`` object on the page, in document order."""
    out: list[dict] = []
    for raw in _LD_BLOCK.findall(html or ""):
        text = raw.strip()
        if not text:
            continue
        try:
            document = json.loads(text)
        except json.JSONDecodeError:
            # Some CMSs emit HTML-escaped JSON inside the script element.
            try:
                document = json.loads(unescape(text))
            except json.JSONDecodeError:
                continue
        for obj in _iter_ld_objects(document):
            if _is_job_posting(obj):
                out.append(obj)
    return out


# ------------------------------------------------------------------ microdata


class _Scope:
    """One open ``itemscope``: its collected properties and where it started."""

    __slots__ = ("data", "depth", "prop")

    def __init__(self, depth: int, prop: str | None) -> None:
        self.data: dict = {}
        self.depth = depth
        self.prop = prop


class _MicrodataParser(HTMLParser):
    """Collect ``itemprop`` values inside each ``JobPosting`` itemscope.

    Nested itemscopes matter and are kept nested: ``hiringOrganization`` and
    ``jobLocation`` are themselves scopes whose payload lives in ``<meta
    itemprop=... content=...>`` children.  A parser that flattens them, or that
    stops collecting once it is inside a property, loses the employer name and
    the location entirely - which is exactly the silent-blank class this file
    exists to close.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.postings: list[dict] = []
        self._depth = 0
        self._scopes: list[_Scope] = []
        self._prop: str | None = None
        self._prop_depth: int | None = None
        self._buffer: list[str] = []

    # -- helpers ---------------------------------------------------------
    def _store(self, prop: str, value) -> None:
        if self._scopes and prop:
            self._scopes[-1].data.setdefault(prop, value)

    def _flush_prop(self) -> None:
        if self._prop is None:
            return
        value = " ".join("".join(self._buffer).split())
        if value:
            self._store(self._prop, value)
        self._prop = None
        self._prop_depth = None
        self._buffer = []

    # -- HTMLParser hooks ------------------------------------------------
    def handle_startendtag(self, tag, attrs):
        self._handle_attrs(tag, dict(attrs), void=True)

    def handle_starttag(self, tag, attrs):
        if tag in _SELF_CLOSING:
            self._handle_attrs(tag, dict(attrs), void=True)
            return
        self._depth += 1
        self._handle_attrs(tag, dict(attrs), void=False)

    def _handle_attrs(self, tag, attrs, void: bool) -> None:
        itemtype = (attrs.get("itemtype") or "").lower()
        has_scope = "itemscope" in attrs or bool(itemtype)
        prop = attrs.get("itemprop")

        if has_scope and not void:
            if itemtype.endswith("/" + JOB_POSTING_TYPE) and not self._scopes:
                self._flush_prop()
                self._scopes.append(_Scope(self._depth, None))
                return
            if self._scopes:
                # A nested scope replaces any text capture that was running for
                # the same property; its children carry the real values.
                if self._prop is not None and prop == self._prop:
                    self._prop = None
                    self._prop_depth = None
                    self._buffer = []
                self._scopes.append(_Scope(self._depth, prop))
                return
            return

        if not self._scopes or not prop or self._prop is not None:
            return
        literal = attrs.get("content")
        if literal is None:
            literal = attrs.get("datetime")
        if literal is None and tag in ("a", "link"):
            literal = attrs.get("href")
        if literal is not None:
            self._store(prop, str(literal).strip())
            return
        if void:
            return
        self._prop = prop
        self._prop_depth = self._depth
        self._buffer = []

    def handle_data(self, data):
        if self._prop is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag):
        if tag in _SELF_CLOSING:
            return
        if self._prop is not None and self._prop_depth == self._depth:
            self._flush_prop()
        while self._scopes and self._scopes[-1].depth == self._depth:
            scope = self._scopes.pop()
            if self._scopes and scope.prop:
                self._scopes[-1].data.setdefault(scope.prop, scope.data)
            elif not self._scopes:
                if scope.data:
                    self.postings.append(scope.data)
        self._depth -= 1

    def close(self):
        super().close()
        self._flush_prop()
        while self._scopes:
            scope = self._scopes.pop()
            if self._scopes and scope.prop:
                self._scopes[-1].data.setdefault(scope.prop, scope.data)
            elif not self._scopes and scope.data:
                self.postings.append(scope.data)


def extract_microdata_postings(html: str) -> list[dict]:
    parser = _MicrodataParser()
    try:
        parser.feed(html or "")
        parser.close()
    except Exception:
        return parser.postings
    return parser.postings


# -------------------------------------------------------------------- mapping


def _first_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        for item in value:
            text = _first_text(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        for key in ("name", "value", "@value", "@id", "text", "title"):
            if key in value:
                text = _first_text(value[key])
                if text:
                    return text
    return ""


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return None


def _organisation(obj: dict) -> str:
    return _first_text(obj.get("hiringOrganization")) or _first_text(obj.get("author"))


def _location(obj: dict) -> str:
    location = obj.get("jobLocation")
    candidates = location if isinstance(location, list) else [location]
    parts: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, dict):
            address = candidate.get("address")
            if isinstance(address, dict):
                for key in ("addressLocality", "addressRegion", "addressCountry"):
                    text = _first_text(address.get(key))
                    if text:
                        parts.append(text)
            elif address:
                parts.append(_first_text(address))
            if not parts:
                parts.append(_first_text(candidate))
        elif candidate:
            parts.append(_first_text(candidate))
        if parts:
            break
    if not parts:
        # Microdata flattens the nested Place/PostalAddress itemscope, so the
        # address properties arrive as siblings of the posting's own properties.
        for key in ("addressLocality", "addressRegion", "addressCountry"):
            text = _first_text(obj.get(key))
            if text:
                parts.append(text)
    if not parts:
        for key in ("address", "jobLocationType"):
            text = _first_text(obj.get(key))
            if text:
                parts.append(text)
                break
    seen: list[str] = []
    for part in parts:
        if part and part not in seen:
            seen.append(part)
    return ", ".join(seen)


def _structured_url(value: Any, page_url: str) -> str:
    candidate = _first_text(value).strip()
    if not candidate.lower().startswith(("http://", "https://")):
        return ""
    try:
        page = urlsplit(page_url)
        target = urlsplit(candidate)
    except ValueError:
        return ""
    # A generic source may safely prefer a canonical/direct URL only when it
    # stays on the fetched site's origin. Cross-origin application links can be
    # a tracker, a stale copy, or a different policy boundary.
    page_origin = (page.scheme.lower(), page.netloc.lower())
    target_origin = (target.scheme.lower(), target.netloc.lower())
    if page.netloc and target_origin != page_origin:
        return ""
    return candidate


def _apply_url(obj: dict, page_url: str) -> str:
    # Prefer structured canonical/direct links when they remain on the same
    # origin. Fall back to the page we actually fetched for an auditable URL.
    for key in ("url", "sameAs", "mainEntityOfPage"):
        selected = _structured_url(obj.get(key), page_url)
        if selected:
            return selected
    return page_url if page_url else ""


def to_raw_posting(obj: dict, company: str, page_url: str, source: str,
                   sectors: list[str] | None = None) -> RawPosting | None:
    """Map one schema.org JobPosting onto a RawPosting, or None if unusable."""
    title = _first_text(obj.get("title")) or _first_text(obj.get("name"))
    if not title:
        return None
    employer = _organisation(obj) or company
    url = _apply_url(obj, page_url)
    if not url:
        return None
    return RawPosting(
        source=source,
        company=employer or company,
        title=title,
        location=_location(obj),
        url=url,
        jd_text=strip_html(_first_text(obj.get("description"))),
        posted_at=_first_text(obj.get("datePosted")) or _first_text(obj.get("dateCreated")),
        extra={
            "sectors": list(sectors or []),
            "employmentType": _first_text(obj.get("employmentType")),
            "employment_type": _first_text(obj.get("employmentType")),
            "valid_through": _first_text(obj.get("validThrough")),
            "validThrough": _first_text(obj.get("validThrough")),
            "direct_apply": _as_bool(obj.get("directApply")),
            "directApply": _as_bool(obj.get("directApply")),
            "eligibility_to_work_requirement": _first_text(
                obj.get("eligibilityToWorkRequirement")),
            "eligibilityToWorkRequirement": _first_text(
                obj.get("eligibilityToWorkRequirement")),
            "structured_url": _structured_url(
                obj.get("url") or obj.get("sameAs") or obj.get("mainEntityOfPage"), page_url),
            "structured_data": "jsonld" if "@type" in obj else "microdata",
            "page_url": page_url,
        },
    )


def extract_postings(html: str, company: str, page_url: str, source: str,
                     sectors: list[str] | None = None) -> list[RawPosting]:
    """Every JobPosting on one page, from JSON-LD first and microdata second."""
    objects = extract_jsonld_postings(html)
    objects += extract_microdata_postings(html)
    out: list[RawPosting] = []
    seen: set[str] = set()
    for obj in objects:
        posting = to_raw_posting(obj, company, page_url, source, sectors)
        if posting is None:
            continue
        key = f"{posting.title}|{posting.url}"
        if key in seen:
            continue
        seen.add(key)
        out.append(posting)
    return out


# ------------------------------------------------------------- link discovery

_HREF = re.compile(r"""<a[^>]+href\s*=\s*['"]([^'"]+)['"]""", re.IGNORECASE)
_JOB_LINK_HINT = re.compile(
    r"(/jobs?/|/job-|/stelle|/stellenangebot|/vacanc|/career|/karriere|/position|/opening|/offer)",
    re.IGNORECASE)

#: Known ATS board signatures.  A careers page that links to one of these is
#: telling us which adapter should really be handling that company.
ATS_HINT = re.compile(
    r"(boards\.greenhouse\.io/[\w.-]+|job-boards\.greenhouse\.io/[\w.-]+"
    r"|jobs\.lever\.co/[\w.-]+|jobs\.ashbyhq\.com/[\w.-]+"
    r"|jobs\.smartrecruiters\.com/[\w.-]+|[\w-]+\.jobs\.personio\.(?:de|com)"
    r"|[\w-]+\.recruitee\.com|[\w-]+\.teamtailor\.com|[\w-]+\.[\w]+\.myworkdayjobs\.com"
    r"|apply\.workable\.com/[\w.-]+|join\.com/companies/[\w.-]+)",
    re.IGNORECASE)


def find_job_links(html: str, page_url: str, limit: int = 25) -> list[str]:
    """Absolute, same-site links from a careers index that look like postings."""
    out: list[str] = []
    seen: set[str] = set()
    page_host = urlsplit(page_url).netloc.lower()
    for href in _HREF.findall(html or ""):
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        absolute = urljoin(page_url, unescape(href))
        if not absolute.startswith("http"):
            continue
        if page_host and urlsplit(absolute).netloc.lower() != page_host:
            continue
        if not _JOB_LINK_HINT.search(absolute):
            continue
        if absolute in seen or absolute.rstrip("/") == (page_url or "").rstrip("/"):
            continue
        seen.add(absolute)
        out.append(absolute)
        if len(out) >= limit:
            break
    return out


def find_ats_boards(html: str) -> list[str]:
    """ATS board URLs a careers page links to, deduplicated, lowercased."""
    seen: list[str] = []
    for match in ATS_HINT.findall(html or ""):
        value = match.lower()
        if value not in seen:
            seen.append(value)
    return seen
