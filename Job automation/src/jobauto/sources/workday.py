"""Workday CXS API source adapter.

Queries public Workday Career Experience Services (CXS) endpoints:
  POST https://{host}/wday/cxs/{tenant}/{board}/jobs
with JSON payload:
  {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": search_text}

Headers:
  {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "..."}

Constructs RawPosting objects with direct application URLs:
  https://{host}/en-US/{board}{externalPath}
and sets:
  source = f"workday:{company_name}"
  title = job.get("title", "")
  location = job.get("locationsText", "")
  posted_at = job.get("postedOn", "")
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from ..models import RawPosting
from ..normalize import strip_html
from . import Recipe

DEFAULT_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
}


def parse_workday_token(tok: str) -> tuple[str, str, str]:
    """Parse a Workday token into (host, tenant, board).

    Supported token structures:
      - 'host|tenant|board' (e.g. 'abb.wd3.myworkdayjobs.com|abb|External_Career_Page')
      - 'tenant|board|host' (e.g. 'abb|External_Career_Page|abb.wd3.myworkdayjobs.com')
      - host with or without https://
    """
    tok = (tok or "").strip()
    parts = [p.strip() for p in tok.split("|")]
    if len(parts) == 1:
        h = parts[0].replace("https://", "").replace("http://", "").rstrip("/")
        tenant = h.split(".")[0] if "." in h else h
        return h, tenant, "Careers"
    if len(parts) == 2:
        h = parts[0].replace("https://", "").replace("http://", "").rstrip("/")
        tenant = h.split(".")[0] if "." in h else h
        return h, tenant, parts[1]

    p0, p1, p2 = parts[0], parts[1], parts[2]
    if "." in p0 or "myworkdayjobs" in p0:
        host, tenant, board = p0, p1, p2
    elif "." in p2 or "myworkdayjobs" in p2:
        tenant, board, host = p0, p1, p2
    else:
        host, tenant, board = p0, p1, p2

    host = host.replace("https://", "").replace("http://", "").rstrip("/")
    return host, tenant, board


def extract_host_and_board_from_url(list_url: str) -> tuple[str, str]:
    """Extract host and board name from a Workday CXS list URL."""
    try:
        parts = urlsplit(list_url)
        host = parts.netloc
        path_segments = [s for s in parts.path.split("/") if s]
        if len(path_segments) >= 4 and path_segments[0] == "wday" and path_segments[1] == "cxs":
            board = path_segments[3]
            return host, board
    except Exception:
        pass
    return "", ""


def build_direct_apply_url(host: str, board: str, external_path: str) -> str:
    """Construct direct application URL from host, board, and externalPath."""
    if not host or not external_path:
        return f"https://{host}" if host else ""
    if external_path.startswith("/en-US/"):
        return f"https://{host}{external_path}"
    clean_path = external_path if external_path.startswith("/") else f"/{external_path}"
    if board:
        return f"https://{host}/en-US/{board}{clean_path}"
    return f"https://{host}{clean_path}"


def parse_workday(recipe: Recipe, payload: dict[str, Any]) -> list[RawPosting]:
    """Map Workday CXS JSON response payload to list of RawPosting."""
    src = f"workday:{recipe.company}"
    out: list[RawPosting] = []
    if not isinstance(payload, dict):
        return out

    host, board = extract_host_and_board_from_url(recipe.list_url)
    job_postings = payload.get("jobPostings", [])
    for j in job_postings:
        title = (j.get("title") or "").strip()
        location = (j.get("locationsText") or "").strip()
        posted_on = str(j.get("postedOn") or "").strip()
        ext_path = j.get("externalPath") or ""
        direct_url = build_direct_apply_url(host, board, ext_path)
        bullet_fields = j.get("bulletFields") or []

        out.append(RawPosting(
            source=src,
            company=recipe.company,
            title=title,
            location=location,
            url=direct_url,
            jd_text="",
            posted_at=posted_on,
            extra={
                "sectors": recipe.sectors,
                "path": ext_path,
                "bulletFields": bullet_fields,
                "needs_detail": True,
            },
        ))
    return out


def fetch_workday(recipe: Recipe, client: Any = None) -> list[RawPosting]:
    """Execute Workday CXS POST search query and follow detail endpoints for full JD."""
    import httpx

    close_client = False
    if client is None:
        client = httpx.Client(
            timeout=20,
            follow_redirects=True,
            headers=DEFAULT_HEADERS,
        )
        close_client = True

    try:
        req_headers = {**DEFAULT_HEADERS, **(recipe.headers or {})}
        body = recipe.body or {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
        resp = client.post(recipe.list_url, json=body, headers=req_headers)
        resp.raise_for_status()
        payload = resp.json()
        postings = parse_workday(recipe, payload)

        if recipe.needs_detail and recipe.detail_url_tmpl:
            for p in postings:
                ext_path = p.extra.get("path")
                if not ext_path:
                    continue
                try:
                    detail_url = recipe.detail_url_tmpl.format(path=ext_path)
                    dresp = client.get(detail_url, headers=req_headers)
                    if dresp.status_code == 200:
                        detail = dresp.json()
                        pinfo = detail.get("jobPostingInfo", {})
                        desc = pinfo.get("jobDescription") or ""
                        if desc:
                            p.jd_text = strip_html(desc)
                        if pinfo.get("externalUrl"):
                            p.url = pinfo.get("externalUrl")
                        if pinfo.get("location") and not p.location:
                            p.location = str(pinfo.get("location"))
                        if pinfo.get("postedOn") and not p.posted_at:
                            p.posted_at = str(pinfo.get("postedOn"))
                except Exception:
                    continue
        return postings
    finally:
        if close_client:
            client.close()
