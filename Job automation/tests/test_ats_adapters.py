"""Unit tests for Workday and Personio ATS adapters."""
from __future__ import annotations

import unittest
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from jobauto.models import RawPosting
from jobauto.sources import Recipe, build_recipes, parse
from jobauto.sources.fetch import (_BoundedCrawler, ResponseTooLarge, RobotsDenied,
                                   fetch_recipe, fetch_recipe_with)
from jobauto.sources.personio import fetch_personio, parse_personio
from jobauto.sources.workday import (
    build_direct_apply_url,
    extract_host_and_board_from_url,
    fetch_workday,
    parse_workday,
    parse_workday_token,
)


class TestBundesagenturAdapter(unittest.TestCase):
    def _fixture(self, name):
        return json.loads((Path(__file__).parent / "fixtures" / name).read_text(encoding="utf-8"))

    def test_v6_fields_and_canonical_apply_url(self):
        from jobauto.sources.bundesagentur import PORTAL, apply_url, parse_list
        recipe = Recipe("Bundesagentur", PORTAL, "https://example.test/v6", sectors=["engineering"])
        rows = parse_list(recipe, self._fixture("bundesagentur_v6_list.json"))
        self.assertEqual(3, len(rows))
        self.assertEqual("INGENIEUR (M/W/D)", rows[0].title)
        self.assertEqual("10000-1207890540-S", rows[0].extra["referenznummer"])
        self.assertEqual(apply_url(rows[0].extra["referenznummer"]), rows[0].url)
        self.assertNotIn("allianz", rows[0].url.lower())

    def test_detail_utf8_and_drift_detector_can_fail(self):
        from jobauto.sources.bundesagentur import detect_drift, parse_detail
        detail = self._fixture("bundesagentur_v4_detail.json")
        self.assertIn("stellenangebotsBeschreibung", detail)
        self.assertNotIn("\ufffd", parse_detail(detail))
        self.assertEqual([], detect_drift(self._fixture("bundesagentur_v6_list.json")))
        mutated = dict(self._fixture("bundesagentur_v6_list.json"))
        mutated.pop("facetten")
        self.assertTrue(detect_drift(mutated))

    def test_403_message_and_cross_origin_key_strip(self):
        from jobauto.sources.bundesagentur import API_KEY_HEADER, DEFAULT_HEADERS, describe_blocked, request
        self.assertIn("rate-limited or route changed", describe_blocked(
            403, {"X-API-BLOCKED": "1", "correlation-id": "abc"}))
        self.assertIn("ambiguous", describe_blocked(403, {"correlation-id": "abc"}))

        class Response:
            def __init__(self, status, headers=None):
                self.status_code, self.headers = status, headers or {}

        class Client:
            def __init__(self): self.calls = []
            def get(self, url, headers=None, **kwargs):
                self.calls.append((url, dict(headers or {})))
                if len(self.calls) == 1:
                    return Response(302, {"location": "https://other.example/jobs"})
                return Response(200)

        client = Client()
        request(client, "https://rest.example/jobs", DEFAULT_HEADERS)
        self.assertIn(API_KEY_HEADER, client.calls[0][1])
        self.assertNotIn(API_KEY_HEADER, client.calls[1][1])

    def test_detail_404_is_expired_and_detail_403_is_ambiguous(self):
        from jobauto.sources.bundesagentur import fetch

        class Response:
            def __init__(self, status, payload=None, headers=None):
                self.status_code = status
                self.headers = headers or {}
                self.content = json.dumps(payload or {}).encode("utf-8")

            def json(self):
                return json.loads(self.content.decode("utf-8"))

        class Client:
            def __init__(self, detail_status):
                self.detail_status = detail_status

            def get(self, url, headers=None, **kwargs):
                if "jobdetails" in url:
                    return Response(self.detail_status,
                                    headers={"X-API-BLOCKED": "1", "correlation-id": "r-1"})
                return Response(200, self_payload)

        self_payload = self._fixture("bundesagentur_v6_list.json")
        recipe = Recipe("Bundesagentur", "agg_bundesagentur", "https://example.test/v6")

        rows, counts = fetch(recipe, Client(404), detail_limit=1)
        self.assertEqual(1, counts["expired"])
        self.assertEqual("expired", rows[0].extra["detail_status"])

        rows, counts = fetch(recipe, Client(403), detail_limit=1)
        self.assertEqual(1, counts["detail_failed"])
        self.assertEqual("ambiguous_403", rows[0].extra["detail_status"])
        self.assertIn("ambiguous", rows[0].extra["detail_error"])


class TestCustomStructuredData(unittest.TestCase):
    def test_three_recorded_vendor_pages_map_structured_fields(self):
        from jobauto.sources.jobposting_html import extract_postings

        fixtures = [
            ("arbeitnow_jobposting.html", "arbeitnow"),
            ("bundesagentur_jobdetail.html", "bundesagentur"),
            ("smartrecruiters_posting.html", "smartrecruiters"),
        ]
        for filename, vendor in fixtures:
            page = Path(__file__).parent / "fixtures" / "careers_pages" / filename
            rows = extract_postings(page.read_text(encoding="utf-8"), "Fixture Co",
                                    f"https://{vendor}.example/jobs/1",
                                    f"custom:{vendor}")
            self.assertTrue(rows, vendor)
            row = rows[0]
            self.assertTrue(row.title)
            self.assertTrue(row.company)
            self.assertTrue(row.location)
            self.assertTrue(row.posted_at)
            self.assertEqual(f"https://{vendor}.example/jobs/1", row.url)

    def test_structured_direct_url_and_semantics_are_preserved(self):
        from jobauto.sources.jobposting_html import to_raw_posting
        row = to_raw_posting({
            "@type": "JobPosting", "title": "Systems Engineer",
            "description": "Build systems", "url": "https://example.test/jobs/42",
            "directApply": True, "validThrough": "2026-12-31",
            "employmentType": "FULL_TIME",
            "eligibilityToWorkRequirement": "EU work authorization",
        }, "Fixture Co", "https://example.test/careers", "custom:test")
        self.assertEqual("https://example.test/jobs/42", row.url)
        self.assertTrue(row.extra["direct_apply"])
        self.assertEqual("2026-12-31", row.extra["valid_through"])
        self.assertEqual("FULL_TIME", row.extra["employment_type"])
        self.assertEqual("EU work authorization", row.extra["eligibility_to_work_requirement"])
        external = to_raw_posting({
            "@type": "JobPosting", "title": "External Copy",
            "description": "Build systems", "url": "https://tracker.example/apply/42",
        }, "Fixture Co", "https://example.test/careers", "custom:test")
        self.assertEqual("https://example.test/careers", external.url)

    def test_custom_timeout_continues_to_following_posting_link(self):
        from jobauto.sources.fetch import fetch_custom

        class Response:
            def __init__(self, status, body=b""):
                self.status_code, self.content, self.encoding, self.url = status, body, "utf-8", ""
                self.headers = {}

        class Client:
            def __init__(self):
                self.calls = []

            def get(self, url, timeout=None):
                self.calls.append(url)
                if url.endswith("/robots.txt"):
                    return Response(404)
                if url.endswith("/careers"):
                    return Response(200, b'<a href="/opening/1">One</a>'
                                    b'<a href="/opening/2">Two</a>')
                if url.endswith("/opening/1"):
                    raise TimeoutError("one link timed out")
                return Response(200, b'''<script type="application/ld+json">
                    {"@type":"JobPosting","title":"Systems Engineer",
                     "description":"Build systems"}
                </script>''')

        client = Client()
        rows = fetch_custom(Recipe("Fixture Co", "custom", "https://example.test/careers"), client)
        self.assertEqual(1, len(rows))
        self.assertEqual("Systems Engineer", rows[0].title)
        self.assertTrue(any(url.endswith("/opening/1") for url in client.calls))
        self.assertTrue(any(url.endswith("/opening/2") for url in client.calls))

    def test_bounded_crawler_robots_retry_cache_and_response_cap(self):
        class Response:
            def __init__(self, status, body=b"", headers=None):
                self.status_code, self.content = status, body
                self.headers, self.encoding, self.url = headers or {}, "utf-8", ""

        class Client:
            def __init__(self):
                self.calls = []
                self.page_attempts = 0

            def get(self, url, timeout=None):
                self.calls.append(url)
                if url.endswith("/robots.txt"):
                    return Response(200, b"User-agent: *\nDisallow: /private\n")
                if "/private" in url:
                    return Response(200, b"hidden")
                self.page_attempts += 1
                if self.page_attempts == 1:
                    return Response(503, b"retry", {"Retry-After": "2"})
                return Response(200, b"ok")

        sleeps = []
        client = Client()
        crawler = _BoundedCrawler(client, sleep=sleeps.append, clock=lambda: 0.0)
        with self.assertRaises(RobotsDenied):
            crawler.get("https://example.test/private")
        self.assertEqual(0, client.page_attempts)
        self.assertEqual(b"ok", crawler.get("https://example.test/careers").content)
        self.assertEqual(b"ok", crawler.get("https://example.test/careers").content)
        self.assertEqual(2, client.page_attempts)
        self.assertIn(2.0, sleeps)

        huge = Client()
        huge.get = lambda url, timeout=None: Response(404, b"") if url.endswith("robots.txt") else Response(200, b"x" * 20)
        with self.assertRaises(ResponseTooLarge):
            _BoundedCrawler(huge, max_bytes=10).get("https://example.test/careers")

    def test_euraxess_recorded_html_parser_emits_job_cards(self):
        from jobauto.sources.aggregators import parse_euraxess
        html = (Path(__file__).parent / "fixtures" / "careers_pages" /
                "euraxess_search.html").read_text(encoding="utf-8")
        recipe = Recipe("EURAXESS", "agg_euraxess",
                        "https://euraxess.example/jobs/search?keywords=cell")
        rows = parse_euraxess(recipe, html, ["fuel cell"])
        self.assertEqual(1, len(rows))
        self.assertEqual("Fuel Cell Researcher", rows[0].title)
        self.assertEqual("https://euraxess.example/jobs/123", rows[0].url)
        self.assertEqual("Posted 2026-09-10", rows[0].posted_at)

    def test_euraxess_recipe_uses_recorded_html_fetch_path(self):
        html = (Path(__file__).parent / "fixtures" / "careers_pages" /
                "euraxess_search.html").read_text(encoding="utf-8")

        class Response:
            def __init__(self):
                self.status_code = 200
                self.content = html.encode("utf-8")
                self.encoding = "utf-8"

            def raise_for_status(self):
                return None

        class Client:
            def get(self, url, headers=None):
                return Response()

        recipe = Recipe("EURAXESS", "agg_euraxess",
                        "https://euraxess.example/jobs/search?keywords=cell")
        with patch("jobauto.config.load_config", return_value={"include_keywords": ["fuel cell"]}):
            rows = fetch_recipe_with(recipe, Client())
        self.assertEqual(1, len(rows))
        self.assertEqual("unclear", rows[0].extra["commercial_use"])

    def test_nonstandard_vacancy_urls_are_stable_and_collision_resistant(self):
        base = dict(source="custom:fixture", company="Example GmbH",
                    title="Systems Engineer", location="Berlin, Germany",
                    posted_at="2026-09-10")
        first = RawPosting(url="https://jobs.example/openings/a7f?b=2&a=1&utm_source=x", **base)
        duplicate = RawPosting(url="https://jobs.example/openings/a7f?a=1&b=2", **base)
        other = RawPosting(url="https://jobs.example/openings/b8e?a=1&b=2", **base)
        self.assertEqual(first.content_id(), duplicate.content_id())
        self.assertNotEqual(first.content_id(), other.content_id())


class TestWorkdayAdapter(unittest.TestCase):
    def test_parse_workday_token_formats(self):
        # host|tenant|board
        h, t, b = parse_workday_token("abb.wd3.myworkdayjobs.com|abb|External_Career_Page")
        self.assertEqual("abb.wd3.myworkdayjobs.com", h)
        self.assertEqual("abb", t)
        self.assertEqual("External_Career_Page", b)

        # tenant|board|host
        h, t, b = parse_workday_token("rollsroyce|RollsRoyce_Careers|rollsroyce.wd3.myworkdayjobs.com")
        self.assertEqual("rollsroyce.wd3.myworkdayjobs.com", h)
        self.assertEqual("rollsroyce", t)
        self.assertEqual("RollsRoyce_Careers", b)

        # With https:// prefix
        h, t, b = parse_workday_token("https://abb.wd3.myworkdayjobs.com|abb|External_Career_Page")
        self.assertEqual("abb.wd3.myworkdayjobs.com", h)
        self.assertEqual("abb", t)
        self.assertEqual("External_Career_Page", b)

    def test_extract_host_and_board_from_url(self):
        url = "https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/External_Career_Page/jobs"
        host, board = extract_host_and_board_from_url(url)
        self.assertEqual("abb.wd3.myworkdayjobs.com", host)
        self.assertEqual("External_Career_Page", board)

    def test_build_direct_apply_url(self):
        url = build_direct_apply_url(
            "abb.wd3.myworkdayjobs.com",
            "External_Career_Page",
            "/job/Berlin/Engineer_JR123",
        )
        self.assertEqual(
            "https://abb.wd3.myworkdayjobs.com/en-US/External_Career_Page/job/Berlin/Engineer_JR123",
            url,
        )

        # When path already starts with /en-US/
        url2 = build_direct_apply_url(
            "abb.wd3.myworkdayjobs.com",
            "External_Career_Page",
            "/en-US/External_Career_Page/job/Berlin/Engineer_JR123",
        )
        self.assertEqual(
            "https://abb.wd3.myworkdayjobs.com/en-US/External_Career_Page/job/Berlin/Engineer_JR123",
            url2,
        )

    def test_parse_workday(self):
        recipe = Recipe(
            company="ABB",
            portal="workday",
            list_url="https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/External_Career_Page/jobs",
            sectors=["heavy", "rail"],
        )
        payload = {
            "total": 1,
            "jobPostings": [
                {
                    "title": "Senior Fuel Cell Architect",
                    "externalPath": "/job/Mannheim/Senior-Fuel-Cell-Architect_JR999",
                    "locationsText": "Mannheim, Baden-Wurttemberg, Germany",
                    "postedOn": "Posted 5 Days Ago",
                    "bulletFields": ["JR999"],
                }
            ],
        }
        postings = parse_workday(recipe, payload)
        self.assertEqual(1, len(postings))
        p = postings[0]
        self.assertEqual("workday:ABB", p.source)
        self.assertEqual("ABB", p.company)
        self.assertEqual("Senior Fuel Cell Architect", p.title)
        self.assertEqual("Mannheim, Baden-Wurttemberg, Germany", p.location)
        self.assertEqual(
            "https://abb.wd3.myworkdayjobs.com/en-US/External_Career_Page/job/Mannheim/Senior-Fuel-Cell-Architect_JR999",
            p.url,
        )
        self.assertEqual("Posted 5 Days Ago", p.posted_at)
        self.assertEqual(["heavy", "rail"], p.extra.get("sectors"))

    def test_fetch_workday_with_detail(self):
        recipe = Recipe(
            company="ABB",
            portal="workday",
            list_url="https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/External_Career_Page/jobs",
            method="POST",
            body={"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "hydrogen"},
            headers={"Content-Type": "application/json"},
            sectors=["heavy"],
            needs_detail=True,
            detail_url_tmpl="https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/External_Career_Page{path}",
        )

        mock_client = MagicMock()
        mock_list_resp = MagicMock()
        mock_list_resp.status_code = 200
        mock_list_resp.json.return_value = {
            "jobPostings": [
                {
                    "title": "Hydrogen Lead",
                    "externalPath": "/job/Zurich/Lead_JR01",
                    "locationsText": "Zurich, Switzerland",
                    "postedOn": "Posted Today",
                }
            ]
        }

        mock_detail_resp = MagicMock()
        mock_detail_resp.status_code = 200
        mock_detail_resp.json.return_value = {
            "jobPostingInfo": {
                "jobDescription": "<p>Full job description for <b>Hydrogen Lead</b>.</p>",
                "location": "Zurich, Switzerland",
                "postedOn": "Posted Today",
                "externalUrl": "https://abb.wd3.myworkdayjobs.com/en-US/External_Career_Page/job/Zurich/Lead_JR01",
            }
        }

        mock_client.post.return_value = mock_list_resp
        mock_client.get.return_value = mock_detail_resp

        postings = fetch_workday(recipe, client=mock_client)
        self.assertEqual(1, len(postings))
        p = postings[0]
        self.assertEqual("Hydrogen Lead", p.title)
        self.assertIn("Full job description for Hydrogen Lead.", p.jd_text)

    def test_parse_workday_preserves_locations_for_profile_filtering(self):
        recipe = Recipe(
            company="ABB",
            portal="workday",
            list_url="https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/External_Career_Page/jobs",
            sectors=["heavy"],
        )
        payload = {
            "total": 5,
            "jobPostings": [
                {
                    "title": "Engineer US",
                    "locationsText": "Farmington Hills, United States",
                    "externalPath": "/job/1",
                },
                {
                    "title": "Engineer CN",
                    "locationsText": "Shanghai, China",
                    "externalPath": "/job/2",
                },
                {
                    "title": "Engineer IN",
                    "locationsText": "Bangalore, India",
                    "externalPath": "/job/3",
                },
                {
                    "title": "Engineer SG",
                    "locationsText": "Singapore, Singapore",
                    "externalPath": "/job/4",
                },
                {
                    "title": "Engineer DE",
                    "locationsText": "Mannheim, Baden-Württemberg, Germany",
                    "externalPath": "/job/5",
                },
            ],
        }
        postings = parse_workday(recipe, payload)
        # Source adapters preserve the full market; the user's target-country
        # profile is applied centrally by score.hard_filter.
        self.assertEqual(5, len(postings))
        self.assertEqual("Engineer DE", postings[-1].title)

    @unittest.skipUnless((Path(__file__).resolve().parents[1] / "profile" / "config.yml").is_file(),
                         "private country defaults are not part of a public export")
    def test_smartrecruiters_recipe_includes_country_de(self):
        recipes = build_recipes([
            {
                "name": "Bosch",
                "portal": "smartrecruiters",
                "token": "BoschGroup",
                "query": "fuel cell",
            },
            {
                "name": "ENERTRAG",
                "portal": "smartrecruiters",
                "token": "enertrag",
                "query": "Wasserstoff",
            },
        ])
        self.assertEqual(2, len(recipes))
        self.assertIn("country=de", recipes[0].list_url)
        self.assertEqual(
            "https://api.smartrecruiters.com/v1/companies/BoschGroup/postings?limit=100&country=de&q=fuel%20cell",
            recipes[0].list_url,
        )
        self.assertEqual(
            "https://api.smartrecruiters.com/v1/companies/enertrag/postings?limit=100&country=de&q=Wasserstoff",
            recipes[1].list_url,
        )


class TestPersonioAdapter(unittest.TestCase):
    def test_parse_personio(self):
        recipe = Recipe(
            company="H2FLY",
            portal="personio",
            list_url="https://h2fly-gmbh.jobs.personio.de/xml",
            sectors=["aviation"],
        )
        xml = """<?xml version="1.0" encoding="utf-8"?>
        <work-positions>
            <position>
                <id>555123</id>
                <name>Avionics Software Engineer</name>
                <office>Stuttgart</office>
                <department>Flight Systems</department>
                <employmentType>permanent</employmentType>
                <seniority>experienced</seniority>
                <schedule>full-time</schedule>
                <createdAt>2026-06-10T12:00:00+00:00</createdAt>
                <jobDescriptions>
                    <jobDescription>
                        <name>Role Overview</name>
                        <value><![CDATA[<p>Develop safety-critical avionics software for hydrogen flight.</p>]]></value>
                    </jobDescription>
                    <jobDescription>
                        <name>Requirements</name>
                        <value><![CDATA[<ul><li>C/C++ embedded</li><li>DO-178C</li></ul>]]></value>
                    </jobDescription>
                </jobDescriptions>
            </position>
        </work-positions>"""

        postings = parse_personio(recipe, xml)
        self.assertEqual(1, len(postings))
        p = postings[0]
        self.assertEqual("personio:H2FLY", p.source)
        self.assertEqual("H2FLY", p.company)
        self.assertEqual("Avionics Software Engineer", p.title)
        self.assertEqual("Stuttgart, Flight Systems", p.location)
        self.assertEqual("https://h2fly-gmbh.jobs.personio.de/job/555123?language=en", p.url)
        self.assertEqual("2026-06-10T12:00:00+00:00", p.posted_at)
        self.assertIn("Role Overview\nDevelop safety-critical avionics software for hydrogen flight.", p.jd_text)
        self.assertIn("Requirements\nC/C++ embedded\nDO-178C", p.jd_text)
        self.assertEqual("555123", p.extra.get("id"))
        self.assertEqual("permanent", p.extra.get("employmentType"))

    def test_fetch_personio(self):
        recipe = Recipe(
            company="Reverion",
            portal="personio",
            list_url="https://reverion.jobs.personio.de/xml",
            sectors=["heavy"],
        )
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """<?xml version="1.0" encoding="utf-8"?>
        <work-positions>
            <position>
                <id>77701</id>
                <name>Control Systems Engineer</name>
                <office>Eching</office>
                <department>R&amp;D</department>
                <createdAt>2026-07-01T09:00:00+00:00</createdAt>
                <jobDescriptions>
                    <jobDescription>
                        <name>Description</name>
                        <value>Reversible solid oxide cell controls.</value>
                    </jobDescription>
                </jobDescriptions>
            </position>
        </work-positions>"""
        mock_client.get.return_value = mock_resp

        postings = fetch_personio(recipe, client=mock_client)
        self.assertEqual(1, len(postings))
        p = postings[0]
        self.assertEqual("Control Systems Engineer", p.title)
        self.assertEqual("https://reverion.jobs.personio.de/job/77701?language=en", p.url)


class TestFetchDispatch(unittest.TestCase):
    def test_fetch_recipe_dispatches_workday(self):
        recipe = Recipe(
            company="ABB",
            portal="workday",
            list_url="https://abb.wd3.myworkdayjobs.com/wday/cxs/abb/External_Career_Page/jobs",
        )
        with patch("jobauto.sources.workday.fetch_workday") as mock_fetch:
            mock_fetch.return_value = [RawPosting("workday:ABB", "ABB", "Engineer")]
            with patch("jobauto.sources.fetch._client"):
                result = fetch_recipe(recipe)
            mock_fetch.assert_called_once()
            self.assertEqual(1, len(result))

    def test_fetch_recipe_dispatches_personio(self):
        recipe = Recipe(
            company="H2FLY",
            portal="personio",
            list_url="https://h2fly-gmbh.jobs.personio.de/xml",
        )
        with patch("jobauto.sources.personio.fetch_personio") as mock_fetch:
            mock_fetch.return_value = [RawPosting("personio:H2FLY", "H2FLY", "Engineer")]
            with patch("jobauto.sources.fetch._client"):
                result = fetch_recipe(recipe)
            mock_fetch.assert_called_once()
            self.assertEqual(1, len(result))


if __name__ == "__main__":
    unittest.main()
