"""Tests for the get_notifications MCP tool and its helpers.

Covers:
- _parse_time_ago: converting relative timestamps like "5m", "1h", "2d" to minutes
- _parse_notification_line: extracting author, action, and text from a notification
- _extract_notifications_from_page: full page text extraction
- get_notifications tool: integration with mocked browser
"""

from typing import Any, Callable, Coroutine
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP

from linkedin_mcp_server.tools.notifications import (
    _extract_notifications_from_page,
    _parse_notification_line,
    _parse_time_ago,
    register_notification_tools,
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
#  _parse_time_ago
# ============================================================================


class TestParseTimeAgo:
    def test_seconds(self):
        assert _parse_time_ago("19s") == 0

    def test_minutes(self):
        assert _parse_time_ago("5m") == 5

    def test_minutes_double_digit(self):
        assert _parse_time_ago("33m") == 33

    def test_hours(self):
        assert _parse_time_ago("1h") == 60

    def test_hours_multi(self):
        assert _parse_time_ago("14h") == 840

    def test_days(self):
        assert _parse_time_ago("2d") == 2880

    def test_weeks(self):
        assert _parse_time_ago("1w") == 10080

    def test_invalid_returns_none(self):
        assert _parse_time_ago("hello") is None

    def test_empty_returns_none(self):
        assert _parse_time_ago("") is None

    def test_none_returns_none(self):
        assert _parse_time_ago(None) is None


# ============================================================================
#  _parse_notification_line
# ============================================================================


class TestParseNotificationLine:
    def test_simple_post(self):
        line = "Ray Dalio posted: Today, on Valentine's Day, I'd like to reflect."
        result = _parse_notification_line(line)
        assert result is not None
        assert result["author"] == "Ray Dalio"
        assert result["action"] == "posted"
        assert "Valentine" in result["text"]

    def test_repost(self):
        line = (
            "Lewis Walker ➲ reposted Lewis Walker ➲'s post: Is your AI hallucinating?"
        )
        result = _parse_notification_line(line)
        assert result is not None
        assert result["author"] == "Lewis Walker ➲"
        assert result["action"] == "reposted"
        assert "hallucinating" in result["text"]

    def test_event_notification(self):
        line = "NVIDIA AI hosted this event. Watch the recording."
        result = _parse_notification_line(line)
        assert result is not None
        assert result["author"] == "NVIDIA AI"
        assert result["action"] == "hosted this event"

    def test_commented(self):
        line = "John Doe commented on your post: Great insight!"
        result = _parse_notification_line(line)
        assert result is not None
        assert result["author"] == "John Doe"
        assert result["action"] == "commented on your post"

    def test_liked(self):
        line = "Jane Smith liked your post"
        result = _parse_notification_line(line)
        assert result is not None
        assert result["author"] == "Jane Smith"

    def test_status_line_returns_none(self):
        assert _parse_notification_line("Status is online") is None

    def test_empty_line_returns_none(self):
        assert _parse_notification_line("") is None

    def test_filter_tab_returns_none(self):
        assert _parse_notification_line("All") is None
        assert _parse_notification_line("Jobs") is None
        assert _parse_notification_line("My posts") is None
        assert _parse_notification_line("Mentions") is None


# ============================================================================
#  _extract_notifications_from_page
# ============================================================================


def _make_mock_page(
    main_text: str = "",
    url: str = "https://www.linkedin.com/notifications/",
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


# Realistic notifications page text (based on actual scrape)
SAMPLE_NOTIFICATIONS_TEXT = """\
All
Jobs
My posts
Mentions

Unread notification.

Stephen Klein posted: At Curiouser.AI we are doing some extraordinary things and it all begins with a philosophy.

5m

Status is online

Unread notification.

Stefan Michel posted: 95412 learners took my Service Innovation class at LinkedIn Learning with a feedback of 4.7/5.0.

33m

Unread notification.

Ray Dalio posted: Today, on Valentine's Day, I'd like to take the time to reflect on principles for lifelong meaningful relationships.

35m

Lewis Walker ➲ reposted Lewis Walker ➲'s post: Is your AI hallucinating? Here are 10 manifestations to watch for.

45m

NVIDIA AI hosted this event. Watch the recording.
NVIDIA AI hosted this event. Watch the recording.
DGX Spark Live: Your Questions Answered Vol. 2
DGX Spark Live: Your Questions Answered Vol. 2
109 Attendees • 46 Comments

5h

Ben Torben-Nielsen, PhD, MBA posted: Mustafa Suleyman says most white-collar work will be fully automated in 12 to 18 months.

5h

Show more results
"""


MINIMAL_NOTIFICATIONS_TEXT = """\
All
Jobs
My posts
Mentions

Ray Dalio posted: Principles are important.

2h
"""


NO_NOTIFICATIONS_TEXT = """\
All
Jobs
My posts
Mentions

No notifications yet.
"""


class TestExtractNotificationsFromPage:
    async def test_full_page_default_limit(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=10)

        assert isinstance(result, list)
        # Should have multiple notifications (at least 5 from sample text)
        assert len(result) >= 5

    async def test_limit_respected(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=3)

        assert len(result) == 3

    async def test_notification_structure(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=10)

        first = result[0]
        assert "author" in first
        assert "text" in first
        assert "time_ago" in first
        assert "is_unread" in first

    async def test_first_notification_content(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=10)

        first = result[0]
        assert first["author"] == "Stephen Klein"
        assert first["action"] == "posted"
        assert "Curiouser" in first["text"]
        assert first["time_ago"] == "5m"
        assert first["is_unread"] is True

    async def test_unread_vs_read(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=10)

        # First 3 are preceded by "Unread notification."
        assert result[0]["is_unread"] is True
        assert result[1]["is_unread"] is True
        assert result[2]["is_unread"] is True
        # Lewis Walker ➲ repost is not preceded by "Unread notification."
        walker = [n for n in result if "Walker" in n["author"]]
        assert len(walker) == 1
        assert walker[0]["is_unread"] is False

    async def test_status_lines_excluded(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=20)

        authors = [n["author"] for n in result]
        assert "Status is online" not in authors
        # No notification should have author starting with "Status"
        for n in result:
            assert not n["author"].startswith("Status")

    async def test_event_notification_parsed(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=20)

        events = [n for n in result if n["action"] == "hosted this event"]
        assert len(events) == 1
        assert events[0]["author"] == "NVIDIA AI"

    async def test_minimal_page(self):
        page = _make_mock_page(main_text=MINIMAL_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=10)

        assert len(result) == 1
        assert result[0]["author"] == "Ray Dalio"
        assert result[0]["time_ago"] == "2h"

    async def test_no_notifications(self):
        page = _make_mock_page(main_text=NO_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=10)

        assert result == []

    async def test_result_is_list(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=10)
        assert isinstance(result, list)

    async def test_repost_detected(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=10)

        reposts = [n for n in result if n["action"] == "reposted"]
        assert len(reposts) == 1
        assert reposts[0]["author"] == "Lewis Walker ➲"

    async def test_time_ago_minutes_populated(self):
        page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        result = await _extract_notifications_from_page(page, limit=10)

        first = result[0]
        assert first["minutes_ago"] == 5


# ============================================================================
#  get_notifications tool integration
# ============================================================================


class TestNotificationsTool:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_page = _make_mock_page(main_text=SAMPLE_NOTIFICATIONS_TEXT)
        mock_browser = MagicMock()
        mock_browser.page = mock_page

        monkeypatch.setattr(
            "linkedin_mcp_server.tools.notifications.ensure_authenticated",
            AsyncMock(),
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.tools.notifications.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        return mock_page

    async def test_success_default_limit(self, mock_context, mock_deps):
        mcp = FastMCP("test")
        register_notification_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_notifications")
        result = await tool_fn(ctx=mock_context, limit=10)

        assert isinstance(result, dict)
        assert "notifications" in result
        assert isinstance(result["notifications"], list)
        assert len(result["notifications"]) >= 5
        assert "count" in result

    async def test_limit_param(self, mock_context, mock_deps):
        mcp = FastMCP("test")
        register_notification_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_notifications")
        result = await tool_fn(ctx=mock_context, limit=2)

        assert len(result["notifications"]) == 2

    async def test_error_returns_structured_error(self, mock_context, monkeypatch):
        from linkedin_mcp_server.exceptions import SessionExpiredError

        monkeypatch.setattr(
            "linkedin_mcp_server.tools.notifications.ensure_authenticated",
            AsyncMock(side_effect=SessionExpiredError()),
        )

        mcp = FastMCP("test")
        register_notification_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_notifications")
        result = await tool_fn(ctx=mock_context, limit=10)
        assert result["error"] == "session_expired"

    async def test_tool_registered(self, mock_deps):
        mcp = FastMCP("test")
        register_notification_tools(mcp)

        tool = await mcp.get_tool("get_notifications")
        assert tool is not None
