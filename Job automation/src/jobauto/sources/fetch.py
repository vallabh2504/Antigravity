"""httpx execution backend: turn recipes into postings, with honest accounting.

Two rules this module now holds and did not before.

**No source returns an empty list without a recorded reason.**  ``portal: custom``
used to ``return []`` unconditionally, which made 58 of 66 configured companies
dead by construction while the report called them ``agent_only``.  A custom
careers page is now really fetched and read for schema.org job postings; if it
carries none, that is recorded as a zero *with the cause*, not as a silent skip.

**One bad source degrades the run; it never ends it.**  Every recipe is fetched
inside its own guard, its outcome is written to the run ledger, and the loop
continues.  A tool that dies because one upstream moved is a tool that stops
working on a Tuesday for reasons the operator cannot see.
"""
from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from ..models import RawPosting
from . import Recipe, parse
from . import bundesagentur as ba
from . import health as health_mod

DEFAULT_TIMEOUT = 20.0
MAX_REDIRECTS = 5
MAX_RESPONSE_BYTES = 2_000_000
MAX_RETRIES = 2
MIN_HOST_INTERVAL = 0.25

#: How many posting-shaped links to follow from a careers index page.
CUSTOM_CRAWL_LIMIT = 12

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
}


class CrawlError(RuntimeError):
    """A bounded crawler refused or could not safely retrieve a page."""


class RobotsDenied(CrawlError):
    pass


class ResponseTooLarge(CrawlError):
    pass


@dataclass
class _ResponseSnapshot:
    status_code: int
    content: bytes
    headers: dict[str, str]
    url: str
    encoding: str = "utf-8"

    @property
    def text(self) -> str:
        return self.content.decode(self.encoding or "utf-8", errors="replace")


class _BoundedCrawler:
    """Small deterministic HTTP policy layer for custom careers pages.

    It deliberately wraps the injected client so all policy decisions remain
    testable without a live server. Cache entries are scoped to one crawl run.
    """

    def __init__(self, client: Any, *, timeout: float = DEFAULT_TIMEOUT,
                 max_bytes: int = MAX_RESPONSE_BYTES, sleep=time.sleep,
                 clock=time.monotonic) -> None:
        self.client = client
        self.timeout = float(timeout)
        self.max_bytes = int(max_bytes)
        self.sleep = sleep
        self.clock = clock
        self.cache: dict[str, _ResponseSnapshot] = {}
        self.robots: dict[str, RobotFileParser | None] = {}
        self.last_request: dict[str, float] = {}

    @staticmethod
    def _key(url: str) -> str:
        parts = urlsplit(url)
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(),
                           parts.path or "/", parts.query, ""))

    @staticmethod
    def _host(url: str) -> str:
        return urlsplit(url).netloc.lower()

    def _pace(self, url: str) -> None:
        host = self._host(url)
        elapsed = self.clock() - self.last_request.get(host, -float("inf"))
        delay = MIN_HOST_INTERVAL - elapsed
        if delay > 0:
            self.sleep(delay)
        self.last_request[host] = self.clock()

    def _request_once(self, url: str) -> _ResponseSnapshot:
        self._pace(url)
        try:
            response = self.client.get(url, timeout=self.timeout)
        except TypeError:
            # Lightweight fixture clients often do not expose httpx's timeout
            # keyword; the production client always receives it above.
            response = self.client.get(url)
        body = getattr(response, "content", None)
        if not isinstance(body, (bytes, bytearray)):
            body = str(getattr(response, "text", "")).encode("utf-8")
        body = bytes(body)
        if len(body) > self.max_bytes:
            raise ResponseTooLarge(f"{url}: response is {len(body)} bytes; limit is {self.max_bytes}")
        headers = {str(k).lower(): str(v) for k, v in dict(getattr(response, "headers", {}) or {}).items()}
        snapshot = _ResponseSnapshot(
            int(getattr(response, "status_code", 0) or 0), body, headers,
            str(getattr(response, "url", url) or url),
            str(getattr(response, "encoding", "utf-8") or "utf-8"))
        source = urlsplit(url)
        final = urlsplit(snapshot.url)
        if final.netloc and (final.scheme.lower(), final.netloc.lower()) != (
                source.scheme.lower(), source.netloc.lower()):
            raise CrawlError(f"cross-origin redirect refused: {url} -> {snapshot.url}")
        return snapshot

    def _retry_after(self, response: _ResponseSnapshot, attempt: int) -> float:
        raw = response.headers.get("retry-after", "").strip()
        if raw:
            try:
                return max(0.0, min(30.0, float(raw)))
            except ValueError:
                try:
                    target = parsedate_to_datetime(raw).timestamp()
                    return max(0.0, min(30.0, target - time.time()))
                except (TypeError, ValueError, OverflowError):
                    pass
        return min(30.0, 2.0 ** attempt)

    def _request(self, url: str, *, check_robots: bool = True) -> _ResponseSnapshot:
        key = self._key(url)
        if key in self.cache:
            return self.cache[key]
        if check_robots and not self.allowed(url):
            raise RobotsDenied(f"robots.txt disallows {url}")
        response = None
        for attempt in range(MAX_RETRIES + 1):
            response = self._request_once(url)
            if response.status_code not in (429, 503) or attempt >= MAX_RETRIES:
                break
            self.sleep(self._retry_after(response, attempt))
        self.cache[key] = response
        return response

    def allowed(self, url: str) -> bool:
        host = self._host(url)
        if host not in self.robots:
            robots_url = urlunsplit((urlsplit(url).scheme or "https", host,
                                     "/robots.txt", "", ""))
            try:
                response = self._request(robots_url, check_robots=False)
            except ResponseTooLarge:
                # A policy that exceeds the same response cap as a posting is
                # not safe to ignore: make the source failure visible rather
                # than silently treating the policy as absent.
                raise
            except Exception:
                # A missing/unreachable policy is not a successful policy
                # retrieval; the page request remains visible to health.
                self.robots[host] = None
            else:
                if response.status_code == 200:
                    parser = RobotFileParser()
                    parser.set_url(robots_url)
                    parser.parse(response.text.splitlines())
                    self.robots[host] = parser
                else:
                    self.robots[host] = None
        parser = self.robots.get(host)
        return parser is None or parser.can_fetch(BROWSER_HEADERS["User-Agent"], url)

    def get(self, url: str) -> _ResponseSnapshot:
        return self._request(url)


def _client():
    import httpx  # lazy: only needed on the httpx backend
    # follow_redirects: many careers pages 301/302/308 to a trailing-slash variant;
    # without it every one of them fails. A browser-like UA: some hosts 403 a bare client.
    return httpx.Client(timeout=DEFAULT_TIMEOUT, follow_redirects=True,
                        max_redirects=MAX_REDIRECTS,
                        headers=dict(BROWSER_HEADERS))


class EmptySource(RuntimeError):
    """A source ran, answered, and carried nothing this adapter could read.

    This is not an error in the run, but it is not a success either, and the
    difference has to reach the report.  ``fetch_all_with_health`` records it as
    an attempted source with ``jobs_yielded == 0`` and this message as the cause.
    """


def fetch_custom(recipe: Recipe, client: Any) -> list[RawPosting]:
    """Read a company's own careers page for schema.org job postings.

    Strategy, cheapest first: read the landing page's structured data; if it has
    none, follow the posting-shaped links it exposes and read those.  Anything
    the page says about an ATS board it really uses is attached to the result so
    the operator can repoint the company at a proper adapter.

    Measured ceiling, stated rather than discovered later: on 2026-09-16 all 58
    configured ``custom`` careers pages were client-rendered search applications
    whose served HTML contains no posting at all.  This path therefore raises
    ``EmptySource`` for them - loudly, with the ATS hints it found - instead of
    returning a zero that reads as success.
    """
    from .jobposting_html import extract_postings, find_ats_boards, find_job_links

    url = (recipe.list_url or "").strip()
    if not url:
        raise EmptySource(f"{recipe.company}: no careers_url configured for portal 'custom'")

    source = f"custom:{recipe.company}"
    crawler = client if isinstance(client, _BoundedCrawler) else _BoundedCrawler(client)
    response = crawler.get(url)
    status = int(getattr(response, "status_code", 0) or 0)
    if status != 200:
        raise RuntimeError(f"{recipe.company}: careers page returned HTTP {status} for {url}")
    html = _text(response)

    postings = extract_postings(html, recipe.company, url, source, recipe.sectors)
    if postings:
        return postings

    seen_urls = set()
    link_errors: list[str] = []
    for link in find_job_links(html, url, limit=CUSTOM_CRAWL_LIMIT):
        if link in seen_urls:
            continue
        seen_urls.add(link)
        try:
            sub = crawler.get(link)
            if int(getattr(sub, "status_code", 0) or 0) != 200:
                continue
            postings.extend(extract_postings(_text(sub), recipe.company, link,
                                             source, recipe.sectors))
        except CrawlError:
            raise
        except Exception:
            link_errors.append(f"{link}: request failed")
            continue
        if len(postings) >= 50:
            break
    if postings:
        return postings

    boards = find_ats_boards(html)
    hint = (f" The page links to an ATS board ({', '.join(boards[:3])}); "
            f"configure that portal for this company instead."
            if boards else
            " The page served no schema.org JobPosting and no posting-shaped links, "
            "which is what a client-rendered careers search looks like over plain HTTP; "
            "use the agent backend (`jobauto manifest`) for this company.")
    if link_errors:
        hint += f" {len(link_errors)} posting link request(s) failed or timed out."
    raise EmptySource(f"{recipe.company}: no postings extractable from {url}.{hint}")


def _text(response: Any) -> str:
    body = getattr(response, "content", None)
    if isinstance(body, (bytes, bytearray)):
        encoding = getattr(response, "encoding", None) or "utf-8"
        try:
            return bytes(body).decode(encoding, errors="replace")
        except LookupError:
            return bytes(body).decode("utf-8", errors="replace")
    return response.text


def fetch_recipe(recipe: Recipe) -> list[RawPosting]:
    with _client() as client:
        return fetch_recipe_with(recipe, client)


def fetch_recipe_with(recipe: Recipe, client: Any) -> list[RawPosting]:
    """Fetch one recipe on an existing client. Raises on any failure."""
    if recipe.portal == "custom":
        return fetch_custom(recipe, client)
    if recipe.portal == "workday":
        from .workday import fetch_workday
        return fetch_workday(recipe, client=client)
    if recipe.portal == "personio":
        from .personio import fetch_personio
        return fetch_personio(recipe, client=client)
    if recipe.portal == ba.PORTAL:
        postings, counts = ba.fetch(recipe, client)
        for posting in postings:
            posting.extra.setdefault("detail_counts", counts)
        return postings

    if recipe.method == "POST":
        resp = client.post(recipe.list_url, json=recipe.body or {}, headers=recipe.headers)
    else:
        resp = client.get(recipe.list_url, headers=recipe.headers)
    resp.raise_for_status()
    if recipe.portal == "agg_euraxess":
        from .aggregators import parse_euraxess
        from .. import config as cfg
        try:
            keywords = cfg.load_config().get("include_keywords", [])
        except Exception:
            keywords = []
        return parse_euraxess(recipe, _text(resp), keywords)
    payload: Any = resp.json()
    if recipe.portal.startswith("agg_"):
        from .aggregators import parse_aggregator
        from .. import config as cfg
        try:
            keywords = cfg.load_config().get("include_keywords", [])
        except Exception:
            keywords = []
        postings = parse_aggregator(recipe, payload, keywords)
    else:
        postings = parse(recipe, payload)
    if recipe.needs_detail and recipe.detail_url_tmpl:
        for p in postings:
            try:
                if recipe.portal == "smartrecruiters" and p.extra.get("id"):
                    d = client.get(recipe.detail_url_tmpl.format(id=p.extra["id"])).json()
                    p.jd_text = _smartrecruiters_jd(d)
                    p.url = d.get("applyUrl") or p.url
            except Exception:
                continue
    return postings


def _smartrecruiters_jd(detail: dict) -> str:
    from ..normalize import strip_html
    secs = (detail.get("jobAd") or {}).get("sections") or {}
    parts = [strip_html((secs.get(k) or {}).get("text", "")) for k in
             ("companyDescription", "jobDescription", "qualifications", "additionalInformation")]
    return "\n\n".join(p for p in parts if p)


def fetch_all(recipes: list[Recipe]) -> list[RawPosting]:
    postings, _ = fetch_all_with_health(recipes)
    return postings


def fetch_all_with_health(recipes: list[Recipe], run: health_mod.SourceRun | None = None,
                          client: Any = None) -> tuple[list[RawPosting], dict[str, Any]]:
    """Fetch every recipe and return the postings plus the run ledger's summary.

    The returned health dict is **bound** to the ledger: a source that runs after
    this function returns - JobSpy has its own fetch path and is called next -
    still lands in the same dict, and therefore in ``source_run.json``.
    """
    ledger = run or health_mod.start_run()
    out: list[RawPosting] = []
    owns_client = client is None
    client = client or _client()
    try:
        for recipe in recipes:
            source = f"{recipe.portal}:{recipe.company}"
            try:
                rows = fetch_recipe_with(recipe, client)
            except EmptySource as exc:
                ledger.record(source, attempted=True, ok=False, jobs_yielded=0,
                              status="empty", error=str(exc),
                              company=recipe.company, portal=recipe.portal)
            except Exception as exc:  # one bad source never ends the run
                ledger.failure(source, f"{type(exc).__name__}: {exc}",
                               company=recipe.company, portal=recipe.portal)
            else:
                out.extend(rows)
                if rows:
                    ledger.ok(source, len(rows), company=recipe.company, portal=recipe.portal)
                else:
                    # HTTP 200 with no parseable postings is not a healthy
                    # source. Keep the run going, but record why the source
                    # contributes a silent zero.
                    ledger.record(source, attempted=True, ok=False, jobs_yielded=0,
                                  status="empty",
                                  error=(f"{recipe.portal} answered successfully but yielded "
                                         "no parseable postings"),
                                  company=recipe.company, portal=recipe.portal)
    finally:
        if owns_client:
            client.close()

    health = ledger.bind({})
    return out, health


def manifest(recipes: list[Recipe]) -> list[dict]:
    """For the agent backend: the exact requests to make per company."""
    return [
        {"company": r.company, "portal": r.portal, "method": r.method,
         "url": r.list_url, "body": r.body, "needs_detail": r.needs_detail,
         "detail_url_tmpl": r.detail_url_tmpl, "sectors": r.sectors}
        for r in recipes
    ]
