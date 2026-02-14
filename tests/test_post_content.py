"""Tests for the get_post_content MCP tool and its helpers.

Covers:
- _parse_engagement_count: parsing engagement numbers from aria-labels
- _extract_post_content_from_page: extracting full post data from DOM
- get_post_content tool: integration with mocked browser
"""

from typing import Any, Callable, Coroutine
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP

from mcp_linkedin_server.tools.post_content import (
    _extract_post_content_from_page,
    _parse_engagement_count,
    register_post_content_tools,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def get_tool_fn(
    mcp: FastMCP, name: str
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    tool = await mcp.get_tool(name)
    if tool is None:
        raise ValueError(f"Tool '{name}' not found")
    return tool.fn  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Mock page builder
# ---------------------------------------------------------------------------

# Realistic data extracted from actual LinkedIn post pages
SAMPLE_POST_DATA = {
    "text": (
        "This FT satellite image shows TSMC's Arizona footprint nearly doubling, "
        "from 1,100 acres (acquired 2020) to 2,000 acres with the new 900-acre "
        "plot (acquired 2026).\n\n"
        "The image makes tangible what the $660B hyperscaler capex and TSMC "
        "expansion numbers mean physically: thousands of acres of Arizona desert "
        "being transformed into the chip manufacturing base for American AI.\n\n"
        "Every Nvidia GPU powering ChatGPT, every Apple chip in iPhones, flows "
        "through facilities like this."
    ),
    "author": "Gennaro Cuofano",
    "headline": "CRO at WordLift | Founder of The Business Engineer",
    "time_raw": "3 minutes ago \u2022 Visible to anyone on or off LinkedIn",
    "reactions_label": "142 reactions",
    "comments_label": "23 comments",
    "reposts_label": "8 reposts",
    "author_profile_url": "/in/gennarocuofano",
}

SAMPLE_POST_MINIMAL = {
    "text": "Simple post with no engagement.",
    "author": "Test User",
    "headline": "Engineer at TestCo",
    "time_raw": "2 hours ago \u2022 Visible to anyone on or off LinkedIn",
    "reactions_label": "",
    "comments_label": "",
    "reposts_label": "",
    "author_profile_url": "/in/testuser",
}


def _make_mock_post_page(data: dict | None = None) -> MagicMock:
    """Build a mock page that returns structured post data from evaluate()."""
    if data is None:
        data = SAMPLE_POST_DATA

    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.wait_for_timeout = AsyncMock()

    async def _mock_evaluate(js_code: str):
        # The JS extraction returns a dict with post content fields
        return {
            "text": data.get("text", ""),
            "author": data.get("author", ""),
            "headline": data.get("headline", ""),
            "time_raw": data.get("time_raw", ""),
            "reactions_label": data.get("reactions_label", ""),
            "comments_label": data.get("comments_label", ""),
            "reposts_label": data.get("reposts_label", ""),
            "author_profile_url": data.get("author_profile_url", ""),
        }

    page.evaluate = AsyncMock(side_effect=_mock_evaluate)
    return page


# ============================================================================
#  _parse_engagement_count
# ============================================================================


class TestParseEngagementCount:
    def test_simple_number(self):
        assert _parse_engagement_count("142 reactions") == 142

    def test_with_commas(self):
        assert _parse_engagement_count("1,823 reactions") == 1823

    def test_single_digit(self):
        assert _parse_engagement_count("3 reactions") == 3

    def test_comments(self):
        assert _parse_engagement_count("23 comments") == 23

    def test_reposts(self):
        assert _parse_engagement_count("8 reposts") == 8

    def test_empty_returns_none(self):
        assert _parse_engagement_count("") is None

    def test_none_returns_none(self):
        assert _parse_engagement_count(None) is None

    def test_no_number_returns_none(self):
        assert _parse_engagement_count("Like") is None

    def test_just_number(self):
        assert _parse_engagement_count("42") == 42

    def test_number_with_k_suffix(self):
        assert _parse_engagement_count("1.2K reactions") == 1200

    def test_number_with_m_suffix(self):
        assert _parse_engagement_count("2.5M reactions") == 2500000


# ============================================================================
#  _extract_post_content_from_page
# ============================================================================


class TestExtractPostContentFromPage:
    async def test_returns_full_text(self):
        page = _make_mock_post_page()
        result = await _extract_post_content_from_page(page)

        assert "TSMC" in result["text"]
        assert "Arizona" in result["text"]

    async def test_returns_author(self):
        page = _make_mock_post_page()
        result = await _extract_post_content_from_page(page)

        assert result["author"] == "Gennaro Cuofano"

    async def test_returns_headline(self):
        page = _make_mock_post_page()
        result = await _extract_post_content_from_page(page)

        assert (
            result["author_headline"]
            == "CRO at WordLift | Founder of The Business Engineer"
        )

    async def test_returns_linkedin_username(self):
        page = _make_mock_post_page()
        result = await _extract_post_content_from_page(page)

        assert result["linkedin_username"] == "gennarocuofano"

    async def test_linkedin_username_none_when_missing(self):
        page = _make_mock_post_page(
            data={
                "text": "No link post",
                "author": "Unknown",
                "headline": "",
                "time_raw": "",
                "reactions_label": "",
                "comments_label": "",
                "reposts_label": "",
                "author_profile_url": "",
            }
        )
        result = await _extract_post_content_from_page(page)

        assert result["linkedin_username"] is None

    async def test_linkedin_username_from_company(self):
        page = _make_mock_post_page(
            data={
                "text": "Company post",
                "author": "NVIDIA",
                "headline": "Tech company",
                "time_raw": "1 hour ago",
                "reactions_label": "",
                "comments_label": "",
                "reposts_label": "",
                "author_profile_url": "/company/nvidia",
            }
        )
        result = await _extract_post_content_from_page(page)

        assert result["linkedin_username"] == "nvidia"

    async def test_returns_reactions_count(self):
        page = _make_mock_post_page()
        result = await _extract_post_content_from_page(page)

        assert result["reactions_count"] == 142

    async def test_returns_comments_count(self):
        page = _make_mock_post_page()
        result = await _extract_post_content_from_page(page)

        assert result["comments_count"] == 23

    async def test_returns_reposts_count(self):
        page = _make_mock_post_page()
        result = await _extract_post_content_from_page(page)

        assert result["reposts_count"] == 8

    async def test_returns_posted_ago(self):
        page = _make_mock_post_page()
        result = await _extract_post_content_from_page(page)

        assert "3 minutes ago" in result["posted_ago"]

    async def test_result_structure(self):
        page = _make_mock_post_page()
        result = await _extract_post_content_from_page(page)

        expected_keys = {
            "text",
            "author",
            "linkedin_username",
            "author_headline",
            "posted_ago",
            "reactions_count",
            "comments_count",
            "reposts_count",
        }
        assert expected_keys.issubset(result.keys())

    async def test_minimal_post_no_engagement(self):
        page = _make_mock_post_page(data=SAMPLE_POST_MINIMAL)
        result = await _extract_post_content_from_page(page)

        assert result["text"] == "Simple post with no engagement."
        assert result["author"] == "Test User"
        assert result["reactions_count"] is None
        assert result["comments_count"] is None
        assert result["reposts_count"] is None

    async def test_empty_text_returns_empty_string(self):
        page = _make_mock_post_page(
            data={
                "text": "",
                "author": "",
                "headline": "",
                "time_raw": "",
                "reactions_label": "",
                "comments_label": "",
                "reposts_label": "",
            }
        )
        result = await _extract_post_content_from_page(page)

        assert result["text"] == ""
        assert result["author"] == ""

    async def test_evaluate_error_returns_empty_result(self):
        page = MagicMock()
        page.evaluate = AsyncMock(side_effect=Exception("DOM error"))
        result = await _extract_post_content_from_page(page)

        assert result["text"] == ""
        assert result["author"] == ""
        assert result["linkedin_username"] is None
        assert result["reactions_count"] is None


# ============================================================================
#  get_post_content tool integration
# ============================================================================


class TestPostContentTool:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_page = _make_mock_post_page()
        mock_browser = MagicMock()
        mock_browser.page = mock_page

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.post_content.ensure_authenticated",
            AsyncMock(),
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.post_content.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        return mock_page

    async def test_success(self, mock_context, mock_deps):
        mcp = FastMCP("test")
        register_post_content_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_post_content")
        result = await tool_fn(
            post_url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
            ctx=mock_context,
        )

        assert isinstance(result, dict)
        assert "text" in result
        assert "author" in result
        assert "TSMC" in result["text"]
        assert result["author"] == "Gennaro Cuofano"
        assert result["linkedin_username"] == "gennarocuofano"
        assert result["reactions_count"] == 142

    async def test_post_url_returned(self, mock_context, mock_deps):
        mcp = FastMCP("test")
        register_post_content_tools(mcp)
        url = "https://www.linkedin.com/feed/update/urn:li:activity:123/"

        tool_fn = await get_tool_fn(mcp, "get_post_content")
        result = await tool_fn(post_url=url, ctx=mock_context)

        assert result["post_url"] == url

    async def test_error_returns_structured_error(self, mock_context, monkeypatch):
        from mcp_linkedin_server.exceptions import SessionExpiredError

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.post_content.ensure_authenticated",
            AsyncMock(side_effect=SessionExpiredError()),
        )

        mcp = FastMCP("test")
        register_post_content_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_post_content")
        result = await tool_fn(
            post_url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
            ctx=mock_context,
        )
        assert result["error"] == "session_expired"

    async def test_tool_registered(self, mock_deps):
        mcp = FastMCP("test")
        register_post_content_tools(mcp)

        tool = await mcp.get_tool("get_post_content")
        assert tool is not None
