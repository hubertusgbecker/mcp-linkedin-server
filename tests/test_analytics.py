"""Tests for the get_profile_analytics MCP tool and its helpers.

Covers:
- _parse_analytics_number: parsing display numbers like "142", "1,823", "1.2K"
- _extract_analytics_from_page: full dashboard text extraction (two-line format)
- get_profile_analytics tool: integration with mocked browser
"""

from typing import Any, Callable, Coroutine
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP

from mcp_linkedin_server.tools.analytics import (
    _extract_analytics_from_page,
    _parse_analytics_number,
    register_analytics_tools,
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


# ============================================================================
#  _parse_analytics_number
# ============================================================================


class TestParseAnalyticsNumber:
    def test_plain_integer(self):
        assert _parse_analytics_number("142") == 142

    def test_comma_separated(self):
        assert _parse_analytics_number("1,823") == 1823

    def test_k_suffix(self):
        assert _parse_analytics_number("1.2K") == 1200

    def test_k_suffix_no_decimal(self):
        assert _parse_analytics_number("3K") == 3000

    def test_m_suffix(self):
        assert _parse_analytics_number("2.5M") == 2500000

    def test_zero(self):
        assert _parse_analytics_number("0") == 0

    def test_none_returns_none(self):
        assert _parse_analytics_number(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_analytics_number("") is None

    def test_dash_returns_none(self):
        """LinkedIn sometimes shows '--' for unavailable metrics."""
        assert _parse_analytics_number("--") is None

    def test_whitespace_stripped(self):
        assert _parse_analytics_number("  42  ") == 42


# ============================================================================
#  _extract_analytics_from_page
# ============================================================================


def _make_mock_page(
    main_text: str = "",
    url: str = "https://www.linkedin.com/dashboard/",
) -> MagicMock:
    page = MagicMock()
    page.goto = AsyncMock()
    page.url = url
    page.evaluate = AsyncMock(return_value=main_text)
    page.wait_for_timeout = AsyncMock()
    page.wait_for_selector = AsyncMock()
    page.query_selector = AsyncMock(return_value=None)
    page.query_selector_all = AsyncMock(return_value=[])
    return page


# Realistic dashboard text sample (linkedin.com/dashboard/)
# The dashboard uses a two-line format: number on one line, label on the next.
SAMPLE_DASHBOARD_TEXT = """\
Analytics & tools
Saturday, February 14
Analytics

58

Post impressions

16% past 7 days

2,517

Followers

0.2% past 7 days

615

Profile viewers

Past 90 days

39

Search appearances

Previous week
Weekly sharing tracker

Increase your visibility by posting or commenting. We suggest taking 3 actions every week.

Feb 9-Feb 15

3 of 3 actions

Congratulations on achieving the weekly sharing goal.

0 posts
Members who post once per week on average see up to 4x more profile views.
Start a post
3 comments
Members who comment once per week on average see up to 3x more profile views.
Comment on feed
Creator tools

Creator mode gives you more ways to engage with your audience.
"""

MINIMAL_DASHBOARD_TEXT = """\
Analytics & tools
Analytics

5

Profile viewers

0

Post impressions

3

Search appearances

120

Followers
"""

NO_ANALYTICS_TEXT = """\
John Doe
Engineer
Berlin, Germany

Experience
Senior Engineer
"""


class TestExtractAnalyticsFromPage:
    async def test_full_dashboard(self):
        page = _make_mock_page(main_text=SAMPLE_DASHBOARD_TEXT)
        result = await _extract_analytics_from_page(page)

        assert result["profile_views"] == 615
        assert result["post_impressions"] == 58
        assert result["search_appearances"] == 39
        assert result["followers"] == 2517

    async def test_weekly_activity(self):
        page = _make_mock_page(main_text=SAMPLE_DASHBOARD_TEXT)
        result = await _extract_analytics_from_page(page)

        assert result["weekly_posts"] == 0
        assert result["weekly_comments"] == 3

    async def test_minimal_dashboard(self):
        page = _make_mock_page(main_text=MINIMAL_DASHBOARD_TEXT)
        result = await _extract_analytics_from_page(page)

        assert result["profile_views"] == 5
        assert result["post_impressions"] == 0
        assert result["search_appearances"] == 3
        assert result["followers"] == 120

    async def test_no_analytics_section(self):
        """Profile without analytics (not own profile) returns all None."""
        page = _make_mock_page(main_text=NO_ANALYTICS_TEXT)
        result = await _extract_analytics_from_page(page)

        assert result["profile_views"] is None
        assert result["post_impressions"] is None
        assert result["search_appearances"] is None
        assert result["followers"] is None

    async def test_result_shape(self):
        """All expected keys present."""
        page = _make_mock_page(main_text=SAMPLE_DASHBOARD_TEXT)
        result = await _extract_analytics_from_page(page)

        expected_keys = {
            "profile_views",
            "post_impressions",
            "search_appearances",
            "followers",
            "weekly_posts",
            "weekly_comments",
        }
        assert set(result.keys()) == expected_keys

    async def test_missing_weekly_activity(self):
        """Dashboard without weekly activity line returns None for those."""
        page = _make_mock_page(main_text=MINIMAL_DASHBOARD_TEXT)
        result = await _extract_analytics_from_page(page)

        assert result["weekly_posts"] is None
        assert result["weekly_comments"] is None


# ============================================================================
#  get_profile_analytics tool integration
# ============================================================================


class TestProfileAnalyticsTool:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_page = _make_mock_page(main_text=SAMPLE_DASHBOARD_TEXT)
        mock_browser = MagicMock()
        mock_browser.page = mock_page

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.analytics.ensure_authenticated",
            AsyncMock(),
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.analytics.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        return mock_page

    async def test_success(self, mock_context, mock_deps):
        mcp = FastMCP("test")
        register_analytics_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_profile_analytics")
        result = await tool_fn(mock_context)

        assert result["profile_views"] == 615
        assert result["post_impressions"] == 58
        assert result["followers"] == 2517
        assert result["weekly_posts"] == 0

    async def test_error_returns_structured_error(self, mock_context, monkeypatch):
        from mcp_linkedin_server.exceptions import SessionExpiredError

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.analytics.ensure_authenticated",
            AsyncMock(side_effect=SessionExpiredError()),
        )

        mcp = FastMCP("test")
        register_analytics_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_profile_analytics")
        result = await tool_fn(mock_context)
        assert result["error"] == "session_expired"
