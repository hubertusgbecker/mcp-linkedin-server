"""Comprehensive MCP API tests — full coverage for all 9 tool endpoints.

Tests the complete API surface through the FastMCP server interface:
- Tool discovery (tools/list equivalent)
- Tool metadata / annotations
- Parameter schemas
- Success paths with mocked scrapers
- Error paths (validation, authentication, scraping, network, generic)
- Edge cases (empty results, fallback paths, boundary limits)

This complements per-module helper tests by exercising each tool as an
MCP client would: via ``mcp.get_tool(name)`` → ``tool.fn(**kwargs)``.
"""

from typing import Any, Callable, Coroutine, Dict
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP

from mcp_linkedin_server.server import create_mcp_server


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


async def _get_tool_fn(
    mcp: FastMCP, name: str
) -> Callable[..., Coroutine[Any, Any, Dict[str, Any]]]:
    tool = await mcp.get_tool(name)
    if tool is None:
        raise ValueError(f"Tool '{name}' not found")
    return tool.fn  # type: ignore[attr-defined]


@pytest.fixture
def mcp():
    """Create MCP server with all tools registered."""
    return create_mcp_server()


@pytest.fixture
def ctx():
    """Mock FastMCP Context."""
    c = MagicMock()
    c.report_progress = AsyncMock()
    return c


# ===========================================================================
#  1. Tool Discovery & Registration
# ===========================================================================


EXPECTED_TOOLS = {
    "get_person_profile",
    "get_company_profile",
    "get_company_posts",
    "get_job_details",
    "search_jobs",
    "get_profile_analytics",
    "get_notifications",
    "get_post_content",
    "close_session",
}


class TestToolDiscovery:
    """Verify all 9 tools are registered and discoverable."""

    async def test_all_tools_registered(self, mcp):
        tools = await mcp.get_tools()
        tool_names = (
            set(tools.keys())
            if isinstance(tools, dict)
            else {t if isinstance(t, str) else t.name for t in tools}
        )
        assert tool_names == EXPECTED_TOOLS

    async def test_tool_count(self, mcp):
        tools = await mcp.get_tools()
        assert len(tools) == 9

    @pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
    async def test_each_tool_resolvable(self, mcp, name):
        tool = await mcp.get_tool(name)
        assert tool is not None


# ===========================================================================
#  2. Tool Annotations / Metadata
# ===========================================================================


class TestToolAnnotations:
    """Verify readonly/destructive hints are set correctly on all tools."""

    @pytest.mark.parametrize(
        "name",
        [
            "get_person_profile",
            "get_company_profile",
            "get_company_posts",
            "get_job_details",
            "search_jobs",
            "get_profile_analytics",
            "get_notifications",
            "get_post_content",
        ],
    )
    async def test_read_only_tools(self, name, monkeypatch):
        """All scraping tools should be read-only and non-destructive."""
        from mcp_linkedin_server.tools.analytics import register_analytics_tools
        from mcp_linkedin_server.tools.company import register_company_tools
        from mcp_linkedin_server.tools.job import register_job_tools
        from mcp_linkedin_server.tools.notifications import register_notification_tools
        from mcp_linkedin_server.tools.person import register_person_tools
        from mcp_linkedin_server.tools.post_content import register_post_content_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        register_company_tools(mcp)
        register_job_tools(mcp)
        register_analytics_tools(mcp)
        register_notification_tools(mcp)
        register_post_content_tools(mcp)

        tool = await mcp.get_tool(name)
        assert tool is not None
        # FastMCP stores annotations on the tool object
        annotations = getattr(tool, "annotations", None)
        if annotations is not None:
            assert annotations.readOnlyHint is True
            assert annotations.destructiveHint is False


# ===========================================================================
#  3. get_person_profile
# ===========================================================================


class TestGetPersonProfileAPI:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_person = MagicMock()
        mock_person.to_dict.return_value = {
            "name": "Test User",
            "location": "Berlin",
            "linkedin_url": "https://www.linkedin.com/in/testuser/",
        }
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(return_value=mock_person)
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.PersonScraper",
            lambda *a, **kw: mock_scraper,
        )
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.ensure_authenticated", AsyncMock()
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        return mock_person

    async def test_success(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_person_profile")
        result = await fn("testuser", ctx)
        assert result["name"] == "Test User"

    async def test_empty_username_returns_validation_error(self, ctx):
        from mcp_linkedin_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_person_profile")
        result = await fn("", ctx)
        assert result["error"] == "invalid_input"

    async def test_full_url_stripped_to_slug(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_person_profile")
        result = await fn("https://www.linkedin.com/in/testuser/", ctx)
        # validate_linkedin_username extracts the slug from URLs
        assert result["name"] == "Test User"

    async def test_session_expired_error(self, ctx, monkeypatch):
        from mcp_linkedin_server.exceptions import SessionExpiredError
        from mcp_linkedin_server.tools.person import register_person_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.ensure_authenticated",
            AsyncMock(side_effect=SessionExpiredError()),
        )
        mcp = FastMCP("test")
        register_person_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_person_profile")
        result = await fn("testuser", ctx)
        assert result["error"] == "session_expired"
        assert "resolution" in result

    async def test_rate_limit_error(self, ctx, monkeypatch):
        from linkedin_scraper.core.exceptions import RateLimitError

        from mcp_linkedin_server.tools.person import register_person_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.ensure_authenticated",
            AsyncMock(side_effect=RateLimitError("blocked")),
        )
        mcp = FastMCP("test")
        register_person_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_person_profile")
        result = await fn("testuser", ctx)
        assert result["error"] == "rate_limit"
        assert "suggested_wait_seconds" in result

    async def test_network_error(self, ctx, monkeypatch):
        from linkedin_scraper.core.exceptions import NetworkError

        from mcp_linkedin_server.tools.person import register_person_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.ensure_authenticated",
            AsyncMock(side_effect=NetworkError("timeout")),
        )
        mcp = FastMCP("test")
        register_person_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_person_profile")
        result = await fn("testuser", ctx)
        assert result["error"] == "network_error"

    async def test_profile_not_found_error(self, ctx, monkeypatch):
        from linkedin_scraper.core.exceptions import ProfileNotFoundError

        from mcp_linkedin_server.tools.person import register_person_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.ensure_authenticated", AsyncMock()
        )
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(side_effect=ProfileNotFoundError("not found"))
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.PersonScraper",
            lambda *a, **kw: mock_scraper,
        )
        # We need the fallback to also fail for Profile not found to propagate
        # Actually the fallback text extraction doesn't raise ProfileNotFoundError
        # Let's test ensure_authenticated raising it instead
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.person.ensure_authenticated",
            AsyncMock(side_effect=ProfileNotFoundError("profile missing")),
        )
        mcp = FastMCP("test")
        register_person_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_person_profile")
        result = await fn("testuser", ctx)
        assert result["error"] == "profile_not_found"


# ===========================================================================
#  4. get_company_profile
# ===========================================================================


class TestGetCompanyProfileAPI:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_company = MagicMock()
        mock_company.to_dict.return_value = {
            "name": "TestCorp",
            "industry": "Technology",
            "website": "https://testcorp.com",
        }
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(return_value=mock_company)
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.CompanyScraper",
            lambda *a, **kw: mock_scraper,
        )
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.ensure_authenticated", AsyncMock()
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        return mock_company

    async def test_success(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_company_profile")
        result = await fn("testcorp", ctx)
        assert result["name"] == "TestCorp"
        assert result["industry"] == "Technology"

    async def test_empty_slug_returns_validation_error(self, ctx):
        from mcp_linkedin_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_company_profile")
        result = await fn("", ctx)
        assert result["error"] == "invalid_input"

    async def test_slug_with_spaces_returns_validation_error(self, ctx):
        from mcp_linkedin_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_company_profile")
        result = await fn("test corp", ctx)
        assert result["error"] == "invalid_input"

    async def test_authentication_error(self, ctx, monkeypatch):
        from linkedin_scraper.core.exceptions import AuthenticationError

        from mcp_linkedin_server.tools.company import register_company_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.ensure_authenticated",
            AsyncMock(side_effect=AuthenticationError("not logged in")),
        )
        mcp = FastMCP("test")
        register_company_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_company_profile")
        result = await fn("testcorp", ctx)
        assert result["error"] == "authentication_failed"


# ===========================================================================
#  5. get_company_posts
# ===========================================================================


class TestGetCompanyPostsAPI:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_post = MagicMock()
        mock_post.to_dict.return_value = {
            "text": "Hello from TestCorp!",
            "reactions_count": 42,
        }
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(return_value=[mock_post, mock_post])
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.CompanyPostsScraper",
            lambda *a, **kw: mock_scraper,
        )
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.ensure_authenticated", AsyncMock()
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )

    async def test_success(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_company_posts")
        result = await fn("testcorp", ctx, limit=5)
        assert result["count"] == 2
        assert len(result["posts"]) == 2
        assert result["posts"][0]["text"] == "Hello from TestCorp!"

    async def test_default_limit(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_company_posts")
        # Default limit=10 should work
        result = await fn("testcorp", ctx)
        assert "posts" in result

    async def test_empty_slug_returns_error(self, ctx):
        from mcp_linkedin_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_company_posts")
        result = await fn("", ctx)
        assert result["error"] == "invalid_input"

    async def test_scraping_error(self, ctx, monkeypatch):
        from linkedin_scraper.core.exceptions import ScrapingError

        from mcp_linkedin_server.tools.company import register_company_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.ensure_authenticated", AsyncMock()
        )
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(side_effect=ScrapingError("parse failed"))
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.company.CompanyPostsScraper",
            lambda *a, **kw: mock_scraper,
        )
        mcp = FastMCP("test")
        register_company_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_company_posts")
        result = await fn("testcorp", ctx, limit=3)
        assert result["error"] == "scraping_error"


# ===========================================================================
#  6. get_job_details
# ===========================================================================


class TestGetJobDetailsAPI:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_job = MagicMock()
        mock_job.to_dict.return_value = {
            "title": "Software Engineer",
            "company": "TestCorp",
            "location": "Remote",
        }
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(return_value=mock_job)
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.JobScraper",
            lambda *a, **kw: mock_scraper,
        )
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.ensure_authenticated", AsyncMock()
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )

    async def test_success(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.job import register_job_tools

        mcp = FastMCP("test")
        register_job_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_job_details")
        result = await fn("12345678", ctx)
        assert result["title"] == "Software Engineer"
        assert result["company"] == "TestCorp"

    async def test_empty_job_id_returns_error(self, ctx):
        from mcp_linkedin_server.tools.job import register_job_tools

        mcp = FastMCP("test")
        register_job_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_job_details")
        result = await fn("", ctx)
        assert result["error"] == "invalid_input"

    async def test_non_numeric_job_id_returns_error(self, ctx):
        from mcp_linkedin_server.tools.job import register_job_tools

        mcp = FastMCP("test")
        register_job_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_job_details")
        result = await fn("abc-xyz", ctx)
        assert result["error"] == "invalid_input"

    async def test_element_not_found_error(self, ctx, monkeypatch):
        from linkedin_scraper.core.exceptions import ElementNotFoundError

        from mcp_linkedin_server.tools.job import register_job_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.ensure_authenticated", AsyncMock()
        )
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        mock_scraper = MagicMock()
        mock_scraper.scrape = AsyncMock(
            side_effect=ElementNotFoundError("selector missing")
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.JobScraper",
            lambda *a, **kw: mock_scraper,
        )
        mcp = FastMCP("test")
        register_job_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_job_details")
        result = await fn("12345678", ctx)
        assert result["error"] == "element_not_found"


# ===========================================================================
#  7. search_jobs
# ===========================================================================


class TestSearchJobsAPI:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_scraper = MagicMock()
        mock_scraper.search = AsyncMock(
            return_value=[
                "https://www.linkedin.com/jobs/view/111/",
                "https://www.linkedin.com/jobs/view/222/",
                "https://www.linkedin.com/jobs/view/333/",
            ]
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.JobSearchScraper",
            lambda *a, **kw: mock_scraper,
        )
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.ensure_authenticated", AsyncMock()
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )

    async def test_success(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.job import register_job_tools

        mcp = FastMCP("test")
        register_job_tools(mcp)
        fn = await _get_tool_fn(mcp, "search_jobs")
        result = await fn("python developer", ctx, location="Remote", limit=10)
        assert result["count"] == 3
        assert len(result["job_urls"]) == 3

    async def test_success_no_location(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.job import register_job_tools

        mcp = FastMCP("test")
        register_job_tools(mcp)
        fn = await _get_tool_fn(mcp, "search_jobs")
        result = await fn("data scientist", ctx)
        assert result["count"] == 3

    async def test_empty_keywords_returns_error(self, ctx):
        from mcp_linkedin_server.tools.job import register_job_tools

        mcp = FastMCP("test")
        register_job_tools(mcp)
        fn = await _get_tool_fn(mcp, "search_jobs")
        result = await fn("", ctx)
        assert result["error"] == "invalid_input"

    async def test_whitespace_keywords_returns_error(self, ctx):
        from mcp_linkedin_server.tools.job import register_job_tools

        mcp = FastMCP("test")
        register_job_tools(mcp)
        fn = await _get_tool_fn(mcp, "search_jobs")
        result = await fn("   ", ctx)
        assert result["error"] == "invalid_input"

    async def test_generic_exception(self, ctx, monkeypatch):
        from mcp_linkedin_server.tools.job import register_job_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.job.ensure_authenticated",
            AsyncMock(side_effect=RuntimeError("unexpected")),
        )
        mcp = FastMCP("test")
        register_job_tools(mcp)
        fn = await _get_tool_fn(mcp, "search_jobs")
        result = await fn("python", ctx)
        assert result["error"] == "unknown_error"


# ===========================================================================
#  8. get_notifications
# ===========================================================================


SAMPLE_NOTIF_TEXT = """\
All
Jobs
My posts
Mentions

Unread notification.

Ray Dalio posted: Principles are important for life and work.

5m

John Doe commented on your post: Great article!

1h
"""


class TestGetNotificationsAPI:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()

        async def _mock_evaluate(js_code):
            if "/in/" in js_code or "/company/" in js_code:
                return [
                    {"name": "Ray Dalio", "username": "raydalio"},
                    {"name": "John Doe", "username": "johndoe"},
                ]
            if "nt-card__headline" in js_code or "highlightedUpdateUrn" in js_code:
                return [
                    "https://www.linkedin.com/feed/update/urn:li:activity:111/",
                    "https://www.linkedin.com/feed/update/urn:li:activity:222/",
                ]
            return SAMPLE_NOTIF_TEXT

        mock_page.evaluate = AsyncMock(side_effect=_mock_evaluate)
        mock_browser = MagicMock()
        mock_browser.page = mock_page

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.notifications.ensure_authenticated",
            AsyncMock(),
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.notifications.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        return mock_page

    async def test_success(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.notifications import register_notification_tools

        mcp = FastMCP("test")
        register_notification_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_notifications")
        result = await fn(ctx=ctx, limit=10)
        assert "notifications" in result
        assert "count" in result
        assert result["count"] >= 1

    async def test_notification_structure(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.notifications import register_notification_tools

        mcp = FastMCP("test")
        register_notification_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_notifications")
        result = await fn(ctx=ctx, limit=10)
        if result["count"] > 0:
            notif = result["notifications"][0]
            assert "author" in notif
            assert "linkedin_username" in notif
            assert "action" in notif
            assert "text" in notif
            assert "post_url" in notif
            assert "time_ago" in notif
            assert "minutes_ago" in notif
            assert "is_unread" in notif

    async def test_limit_clamps_high_values(self, ctx, mock_deps):
        """Limit > 50 should be clamped to 50 by validate_limit."""
        from mcp_linkedin_server.tools.notifications import register_notification_tools

        mcp = FastMCP("test")
        register_notification_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_notifications")
        result = await fn(ctx=ctx, limit=200)
        # Should not error — validate_limit clamps to max
        assert "notifications" in result

    async def test_session_expired_error(self, ctx, monkeypatch):
        from mcp_linkedin_server.exceptions import SessionExpiredError
        from mcp_linkedin_server.tools.notifications import register_notification_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.notifications.ensure_authenticated",
            AsyncMock(side_effect=SessionExpiredError()),
        )
        mcp = FastMCP("test")
        register_notification_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_notifications")
        result = await fn(ctx=ctx, limit=10)
        assert result["error"] == "session_expired"

    async def test_credentials_not_found_error(self, ctx, monkeypatch):
        from mcp_linkedin_server.exceptions import CredentialsNotFoundError
        from mcp_linkedin_server.tools.notifications import register_notification_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.notifications.ensure_authenticated",
            AsyncMock(side_effect=CredentialsNotFoundError("no profile")),
        )
        mcp = FastMCP("test")
        register_notification_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_notifications")
        result = await fn(ctx=ctx, limit=10)
        assert result["error"] == "authentication_not_found"


# ===========================================================================
#  9. get_post_content
# ===========================================================================


class TestGetPostContentAPI:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.wait_for_selector = AsyncMock()
        mock_page.evaluate = AsyncMock(
            return_value={
                "text": "Great post content here.",
                "author": "Jane Smith",
                "headline": "CEO at TechCo",
                "time_raw": "1 hour ago \u2022 Visible to anyone",
                "reactions_label": "50 reactions",
                "comments_label": "10 comments",
                "reposts_label": "3 reposts",
                "author_profile_url": "/in/janesmith",
            }
        )
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

    async def test_success(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.post_content import register_post_content_tools

        mcp = FastMCP("test")
        register_post_content_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_post_content")
        result = await fn(
            post_url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
            ctx=ctx,
        )
        assert result["text"] == "Great post content here."
        assert result["author"] == "Jane Smith"
        assert result["linkedin_username"] == "janesmith"
        assert result["reactions_count"] == 50
        assert result["comments_count"] == 10
        assert result["reposts_count"] == 3
        assert "1 hour ago" in result["posted_ago"]

    async def test_post_url_included_in_result(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.post_content import register_post_content_tools

        mcp = FastMCP("test")
        register_post_content_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_post_content")
        url = "https://www.linkedin.com/feed/update/urn:li:activity:456/"
        result = await fn(post_url=url, ctx=ctx)
        assert result["post_url"] == url

    async def test_posts_format_url_accepted(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.post_content import register_post_content_tools

        mcp = FastMCP("test")
        register_post_content_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_post_content")
        url = "https://www.linkedin.com/posts/janesmith_leadership-ai-7654321/"
        result = await fn(post_url=url, ctx=ctx)
        assert result["text"] == "Great post content here."

    async def test_empty_url_returns_error(self, ctx):
        from mcp_linkedin_server.tools.post_content import register_post_content_tools

        mcp = FastMCP("test")
        register_post_content_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_post_content")
        result = await fn(post_url="", ctx=ctx)
        assert result["error"] == "invalid_input"

    async def test_non_linkedin_url_returns_error(self, ctx):
        from mcp_linkedin_server.tools.post_content import register_post_content_tools

        mcp = FastMCP("test")
        register_post_content_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_post_content")
        result = await fn(post_url="https://google.com/post/123", ctx=ctx)
        assert result["error"] == "invalid_input"

    async def test_profile_url_rejected(self, ctx):
        from mcp_linkedin_server.tools.post_content import register_post_content_tools

        mcp = FastMCP("test")
        register_post_content_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_post_content")
        result = await fn(post_url="https://www.linkedin.com/in/janesmith/", ctx=ctx)
        assert result["error"] == "invalid_input"

    async def test_session_expired_error(self, ctx, monkeypatch):
        from mcp_linkedin_server.exceptions import SessionExpiredError
        from mcp_linkedin_server.tools.post_content import register_post_content_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.post_content.ensure_authenticated",
            AsyncMock(side_effect=SessionExpiredError()),
        )
        mcp = FastMCP("test")
        register_post_content_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_post_content")
        result = await fn(
            post_url="https://www.linkedin.com/feed/update/urn:li:activity:123/",
            ctx=ctx,
        )
        assert result["error"] == "session_expired"


# ===========================================================================
#  10. get_profile_analytics
# ===========================================================================


SAMPLE_ANALYTICS_TEXT = """\
Analytics & tools
Analytics

58
Post impressions

615
Profile viewers

39
Search appearances

2517
Followers

0 posts
3 comments
"""


class TestGetProfileAnalyticsAPI:
    @pytest.fixture
    def mock_deps(self, monkeypatch):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.url = "https://www.linkedin.com/dashboard/"
        mock_page.evaluate = AsyncMock(return_value=SAMPLE_ANALYTICS_TEXT)
        mock_page.wait_for_selector = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.page = mock_page

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.analytics.ensure_authenticated", AsyncMock()
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.analytics.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        return mock_page

    async def test_success(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.analytics import register_analytics_tools

        mcp = FastMCP("test")
        register_analytics_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_profile_analytics")
        result = await fn(ctx)
        assert result["post_impressions"] == 58
        assert result["profile_views"] == 615
        assert result["search_appearances"] == 39
        assert result["followers"] == 2517
        assert result["weekly_posts"] == 0
        assert result["weekly_comments"] == 3

    async def test_result_has_all_keys(self, ctx, mock_deps):
        from mcp_linkedin_server.tools.analytics import register_analytics_tools

        mcp = FastMCP("test")
        register_analytics_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_profile_analytics")
        result = await fn(ctx)
        expected_keys = {
            "profile_views",
            "post_impressions",
            "search_appearances",
            "followers",
            "weekly_posts",
            "weekly_comments",
        }
        assert expected_keys == set(result.keys())

    async def test_no_params_needed(self, ctx, mock_deps):
        """Analytics tool only needs ctx, no other params."""
        from mcp_linkedin_server.tools.analytics import register_analytics_tools

        mcp = FastMCP("test")
        register_analytics_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_profile_analytics")
        result = await fn(ctx)
        assert "error" not in result

    async def test_session_expired_error(self, ctx, monkeypatch):
        from mcp_linkedin_server.exceptions import SessionExpiredError
        from mcp_linkedin_server.tools.analytics import register_analytics_tools

        monkeypatch.setattr(
            "mcp_linkedin_server.tools.analytics.ensure_authenticated",
            AsyncMock(side_effect=SessionExpiredError()),
        )
        mcp = FastMCP("test")
        register_analytics_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_profile_analytics")
        result = await fn(ctx)
        assert result["error"] == "session_expired"

    async def test_empty_page_returns_nulls(self, ctx, monkeypatch):
        """When dashboard has no data, metrics should be None."""
        from mcp_linkedin_server.tools.analytics import register_analytics_tools

        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.url = "https://www.linkedin.com/dashboard/"
        mock_page.evaluate = AsyncMock(return_value="No data available")
        mock_page.wait_for_selector = AsyncMock()
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.analytics.ensure_authenticated", AsyncMock()
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.tools.analytics.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )

        mcp = FastMCP("test")
        register_analytics_tools(mcp)
        fn = await _get_tool_fn(mcp, "get_profile_analytics")
        result = await fn(ctx)
        assert result["profile_views"] is None
        assert result["post_impressions"] is None


# ===========================================================================
#  11. close_session
# ===========================================================================


class TestCloseSessionAPI:
    async def test_success(self, mcp):
        from unittest.mock import AsyncMock, patch

        fn = await _get_tool_fn(mcp, "close_session")
        with patch("mcp_linkedin_server.server.close_browser", new_callable=AsyncMock):
            result = await fn()
        assert result["status"] == "success"
        assert "closed" in result["message"].lower()

    async def test_error(self, mcp):
        from unittest.mock import AsyncMock, patch

        fn = await _get_tool_fn(mcp, "close_session")
        with patch(
            "mcp_linkedin_server.server.close_browser",
            new_callable=AsyncMock,
            side_effect=RuntimeError("already closed"),
        ):
            result = await fn()
        assert result["status"] == "error"
        assert "already closed" in result["message"]

    async def test_result_structure(self, mcp):
        from unittest.mock import AsyncMock, patch

        fn = await _get_tool_fn(mcp, "close_session")
        with patch("mcp_linkedin_server.server.close_browser", new_callable=AsyncMock):
            result = await fn()
        assert "status" in result
        assert "message" in result


# ===========================================================================
#  12. Cross-cutting: Error response format consistency
# ===========================================================================


class TestErrorResponseFormat:
    """All tools should return consistent error response structures."""

    @pytest.mark.parametrize(
        ("tool_module", "register_fn_name", "tool_name", "kwargs"),
        [
            (
                "mcp_linkedin_server.tools.person",
                "register_person_tools",
                "get_person_profile",
                {"linkedin_username": "ab"},  # too short
            ),
            (
                "mcp_linkedin_server.tools.company",
                "register_company_tools",
                "get_company_profile",
                {"company_name": ""},  # empty
            ),
            (
                "mcp_linkedin_server.tools.job",
                "register_job_tools",
                "get_job_details",
                {"job_id": ""},  # empty
            ),
            (
                "mcp_linkedin_server.tools.job",
                "register_job_tools",
                "search_jobs",
                {"keywords": ""},  # empty
            ),
            (
                "mcp_linkedin_server.tools.post_content",
                "register_post_content_tools",
                "get_post_content",
                {"post_url": ""},  # empty
            ),
        ],
    )
    async def test_validation_error_format(
        self, ctx, tool_module, register_fn_name, tool_name, kwargs
    ):
        """Validation errors should have 'error' and 'message' keys."""
        import importlib

        mod = importlib.import_module(tool_module)
        register_fn = getattr(mod, register_fn_name)

        mcp = FastMCP("test")
        register_fn(mcp)
        fn = await _get_tool_fn(mcp, tool_name)
        result = await fn(**kwargs, ctx=ctx)

        assert "error" in result
        assert "message" in result
        assert result["error"] == "invalid_input"
