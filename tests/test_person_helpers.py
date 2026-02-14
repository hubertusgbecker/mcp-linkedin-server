"""Tests for person tool helper functions and fallback text extraction.

Covers:
- _is_empty_result: empty/non-empty result detection
- _parse_date_range: date string parsing
- _extract_profile_from_page_text: full fallback parser
- get_person_profile fallback flow: scraper → text extraction
"""

import asyncio
from typing import Any, Callable, Coroutine
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP

from linkedin_mcp_server.tools.person import (
    _extract_profile_from_page_text,
    _is_empty_result,
    _parse_date_range,
    register_person_tools,
)


# ---------------------------------------------------------------------------
# Helper: extract registered tool function
# ---------------------------------------------------------------------------


async def get_tool_fn(
    mcp: FastMCP, name: str
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    tool = await mcp.get_tool(name)
    if tool is None:
        raise ValueError(f"Tool '{name}' not found")
    return tool.fn  # type: ignore[attr-defined]


# ============================================================================
#  _is_empty_result
# ============================================================================


class TestIsEmptyResult:
    def test_empty_when_name_missing(self):
        assert _is_empty_result({}) is True

    def test_empty_when_name_is_unknown(self):
        assert _is_empty_result({"name": "Unknown"}) is True

    def test_empty_when_name_is_none(self):
        assert _is_empty_result({"name": None}) is True

    def test_empty_when_name_is_empty_string(self):
        assert _is_empty_result({"name": ""}) is True

    def test_not_empty_with_real_name(self):
        assert _is_empty_result({"name": "Ada Lovelace"}) is False

    def test_not_empty_ignores_other_fields(self):
        """Only 'name' drives the decision."""
        assert _is_empty_result({"name": "X", "about": None}) is False


# ============================================================================
#  _parse_date_range
# ============================================================================


class TestParseDateRange:
    def test_empty_string(self):
        assert _parse_date_range("") == (None, None, None)

    def test_full_range_with_duration(self):
        from_d, to_d, dur = _parse_date_range("Jan 2020 - Present · 5 yrs")
        assert from_d == "Jan 2020"
        assert to_d == "Present"
        assert dur == "5 yrs"

    def test_range_without_duration(self):
        from_d, to_d, dur = _parse_date_range("Mar 2018 - Dec 2020")
        assert from_d == "Mar 2018"
        assert to_d == "Dec 2020"
        assert dur is None

    def test_single_date_no_dash(self):
        from_d, to_d, dur = _parse_date_range("Jun 2022")
        assert from_d == "Jun 2022"
        assert to_d is None
        assert dur is None

    def test_single_date_with_duration(self):
        from_d, to_d, dur = _parse_date_range("2019 · 1 yr")
        assert from_d == "2019"
        assert to_d is None
        assert dur == "1 yr"


# ============================================================================
#  _extract_profile_from_page_text
# ============================================================================


def _make_mock_page(
    title: str = "Ada Lovelace | LinkedIn",
    main_text: str = "",
) -> MagicMock:
    """Create a mock Patchright page with controlled title and innerText."""
    page = MagicMock()
    page.goto = AsyncMock()
    page.title = AsyncMock(return_value=title)
    page.evaluate = AsyncMock(return_value=main_text)
    return page


# A realistic profile page innerText sample (abbreviated).
SAMPLE_MAIN_TEXT = """\
Ada Lovelace
she/her
Mathematician at Babbage Inc | Pioneer of Computing
London, United Kingdom
500+ connections

About
Pioneered the concept of a general-purpose computer.
Wrote the first algorithm intended for machine processing.

Experience
Chief Analyst
Babbage Inc · Full-time
Jan 2020 - Present · 5 yrs
London, United Kingdom

Research Fellow
Royal Society · Contract
Mar 2015 - Dec 2019 · 4 yrs 9 mos

Education
University of London
M.Sc. Computer Science
2013 - 2015

Trinity College
B.A. Mathematics
2010 - 2013
"""


class TestExtractProfileFromPageText:
    async def test_basic_extraction(self):
        page = _make_mock_page(
            title="Ada Lovelace | LinkedIn",
            main_text=SAMPLE_MAIN_TEXT,
        )
        result = await _extract_profile_from_page_text(
            page, "https://www.linkedin.com/in/adalovelace/"
        )

        assert result["name"] == "Ada Lovelace"
        assert result["linkedin_url"] == "https://www.linkedin.com/in/adalovelace/"
        assert result["location"] == "London, United Kingdom"
        assert "general-purpose computer" in (result["about"] or "")

    async def test_experiences_parsed(self):
        page = _make_mock_page(main_text=SAMPLE_MAIN_TEXT)
        result = await _extract_profile_from_page_text(
            page, "https://www.linkedin.com/in/adalovelace/"
        )

        exps = result["experiences"]
        assert len(exps) >= 1
        titles = [e["position_title"] for e in exps]
        assert "Chief Analyst" in titles

    async def test_educations_parsed(self):
        page = _make_mock_page(main_text=SAMPLE_MAIN_TEXT)
        result = await _extract_profile_from_page_text(
            page, "https://www.linkedin.com/in/adalovelace/"
        )

        edus = result["educations"]
        assert len(edus) >= 1
        institutions = [e["institution_name"] for e in edus]
        assert "University of London" in institutions

    async def test_headline_at_parsing(self):
        """Headline with 'at' extracts job_title and company."""
        page = _make_mock_page(main_text=SAMPLE_MAIN_TEXT)
        result = await _extract_profile_from_page_text(
            page, "https://www.linkedin.com/in/adalovelace/"
        )
        assert result["job_title"] == "Mathematician"
        assert result["company"] == "Babbage Inc"

    async def test_empty_page(self):
        """Handles empty innerText gracefully."""
        page = _make_mock_page(title="LinkedIn", main_text="")
        result = await _extract_profile_from_page_text(
            page, "https://www.linkedin.com/in/nobody/"
        )
        assert result["name"] == "LinkedIn"
        assert result["experiences"] == []
        assert result["educations"] == []

    async def test_page_without_about(self):
        """Profile with no About section still works."""
        text = "John Doe\nSoftware Engineer\nBerlin, Germany\n"
        page = _make_mock_page(title="John Doe | LinkedIn", main_text=text)
        result = await _extract_profile_from_page_text(
            page, "https://www.linkedin.com/in/johndoe/"
        )
        assert result["name"] == "John Doe"
        assert result["about"] is None

    async def test_open_to_work_detected(self):
        text = "Jane Doe\n#OpenToWork\nOpen to new opportunities\nBerlin, Germany\n"
        page = _make_mock_page(title="Jane Doe | LinkedIn", main_text=text)
        result = await _extract_profile_from_page_text(
            page, "https://www.linkedin.com/in/janedoe/"
        )
        assert result["open_to_work"] is True

    async def test_result_shape(self):
        """All expected keys are present in the result dict."""
        page = _make_mock_page(main_text=SAMPLE_MAIN_TEXT)
        result = await _extract_profile_from_page_text(
            page, "https://www.linkedin.com/in/adalovelace/"
        )
        expected_keys = {
            "linkedin_url",
            "name",
            "location",
            "about",
            "open_to_work",
            "experiences",
            "educations",
            "interests",
            "accomplishments",
            "contacts",
            "company",
            "job_title",
        }
        assert set(result.keys()) == expected_keys


# ============================================================================
#  get_person_profile fallback flow (integration)
# ============================================================================


class TestPersonToolFallback:
    """Test the fallback from PersonScraper to text extraction."""

    @pytest.fixture
    def mock_browser_page(self, monkeypatch):
        """Mock browser with an async-capable page."""
        mock_page = _make_mock_page(
            title="Fallback User | LinkedIn",
            main_text="Fallback User\nEngineer\nBerlin, Germany\n",
        )
        mock_browser = MagicMock()
        mock_browser.page = mock_page

        for module in ["person"]:
            monkeypatch.setattr(
                f"linkedin_mcp_server.tools.{module}.ensure_authenticated",
                AsyncMock(),
            )
            monkeypatch.setattr(
                f"linkedin_mcp_server.tools.{module}.get_or_create_browser",
                AsyncMock(return_value=mock_browser),
            )
        return mock_page

    async def test_fallback_on_empty_result(
        self, mock_context, mock_browser_page, monkeypatch
    ):
        """When scraper returns empty (name=Unknown), fallback kicks in."""
        mock_person = MagicMock()
        mock_person.to_dict.return_value = {"name": "Unknown", "location": None}
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(return_value=mock_person)
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.person.PersonScraper",
            lambda *a, **kw: mock_scraper,
        )

        mcp = FastMCP("test")
        register_person_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_person_profile")
        result = await tool_fn("fallback-user", mock_context)

        # Should have used fallback — name comes from page title
        assert result["name"] == "Fallback User"
        mock_context.report_progress.assert_awaited()

    async def test_fallback_on_scraper_exception(
        self, mock_context, mock_browser_page, monkeypatch
    ):
        """When scraper raises, fallback kicks in instead of returning error."""
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(
            side_effect=RuntimeError("CSS selector not found")
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.person.PersonScraper",
            lambda *a, **kw: mock_scraper,
        )

        mcp = FastMCP("test")
        register_person_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_person_profile")
        result = await tool_fn("fallback-user", mock_context)

        assert result["name"] == "Fallback User"
        assert "error" not in result

    async def test_no_fallback_on_good_result(
        self, mock_context, mock_browser_page, monkeypatch
    ):
        """When scraper returns valid data, no fallback occurs."""
        mock_person = MagicMock()
        mock_person.to_dict.return_value = {
            "name": "Good User",
            "location": "Munich",
        }
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(return_value=mock_person)
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.person.PersonScraper",
            lambda *a, **kw: mock_scraper,
        )

        mcp = FastMCP("test")
        register_person_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_person_profile")
        result = await tool_fn("good-user", mock_context)

        assert result["name"] == "Good User"
        # Fallback page.goto should NOT have been called
        mock_browser_page.goto.assert_not_awaited()
