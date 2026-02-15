"""Tests that MCP tools return structured validation errors for bad input.

These tests verify the full integration from tool → validation → error_handler.
No browser or network calls are made; validation fails before scraping.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastmcp import FastMCP

from mcp_linkedin_server.tools.company import register_company_tools
from mcp_linkedin_server.tools.job import register_job_tools
from mcp_linkedin_server.tools.person import register_person_tools
from mcp_linkedin_server.tools.post_content import register_post_content_tools


@pytest.fixture
def mcp():
    return FastMCP("test")


@pytest.fixture
def ctx():
    c = MagicMock()
    c.report_progress = AsyncMock()
    return c


# ── person tool ─────────────────────────────────────────────────────────


class TestPersonToolValidation:
    def setup_method(self):
        self.mcp = FastMCP("test")
        register_person_tools(self.mcp)

    @pytest.mark.asyncio
    async def test_empty_username(self, ctx):
        tool = self.mcp._tool_manager._tools["get_person_profile"]
        result = await tool.fn(linkedin_username="", ctx=ctx)
        assert result["error"] == "invalid_input"
        assert "cannot be empty" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_username(self, ctx):
        tool = self.mcp._tool_manager._tools["get_person_profile"]
        result = await tool.fn(linkedin_username="a@b", ctx=ctx)
        assert result["error"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_too_short_username(self, ctx):
        tool = self.mcp._tool_manager._tools["get_person_profile"]
        result = await tool.fn(linkedin_username="ab", ctx=ctx)
        assert result["error"] == "invalid_input"


# ── company tool ────────────────────────────────────────────────────────


class TestCompanyToolValidation:
    def setup_method(self):
        self.mcp = FastMCP("test")
        register_company_tools(self.mcp)

    @pytest.mark.asyncio
    async def test_empty_company_slug(self, ctx):
        tool = self.mcp._tool_manager._tools["get_company_profile"]
        result = await tool.fn(company_name="", ctx=ctx)
        assert result["error"] == "invalid_input"
        assert "cannot be empty" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_company_slug(self, ctx):
        tool = self.mcp._tool_manager._tools["get_company_profile"]
        result = await tool.fn(company_name="company with spaces", ctx=ctx)
        assert result["error"] == "invalid_input"


class TestCompanyPostsToolValidation:
    def setup_method(self):
        self.mcp = FastMCP("test")
        register_company_tools(self.mcp)

    @pytest.mark.asyncio
    async def test_empty_company_slug(self, ctx):
        tool = self.mcp._tool_manager._tools["get_company_posts"]
        result = await tool.fn(company_name="", ctx=ctx)
        assert result["error"] == "invalid_input"


# ── job tools ────────────────────────────────────────────────────────


class TestJobDetailsToolValidation:
    def setup_method(self):
        self.mcp = FastMCP("test")
        register_job_tools(self.mcp)

    @pytest.mark.asyncio
    async def test_empty_job_id(self, ctx):
        tool = self.mcp._tool_manager._tools["get_job_details"]
        result = await tool.fn(job_id="", ctx=ctx)
        assert result["error"] == "invalid_input"
        assert "cannot be empty" in result["message"]

    @pytest.mark.asyncio
    async def test_non_numeric_job_id(self, ctx):
        tool = self.mcp._tool_manager._tools["get_job_details"]
        result = await tool.fn(job_id="abc", ctx=ctx)
        assert result["error"] == "invalid_input"


class TestSearchJobsToolValidation:
    def setup_method(self):
        self.mcp = FastMCP("test")
        register_job_tools(self.mcp)

    @pytest.mark.asyncio
    async def test_empty_keywords(self, ctx):
        tool = self.mcp._tool_manager._tools["search_jobs"]
        result = await tool.fn(keywords="", ctx=ctx)
        assert result["error"] == "invalid_input"
        assert "cannot be empty" in result["message"]

    @pytest.mark.asyncio
    async def test_whitespace_only_keywords(self, ctx):
        tool = self.mcp._tool_manager._tools["search_jobs"]
        result = await tool.fn(keywords="   ", ctx=ctx)
        assert result["error"] == "invalid_input"


# ── post content tool ──────────────────────────────────────────────────


class TestPostContentToolValidation:
    def setup_method(self):
        self.mcp = FastMCP("test")
        register_post_content_tools(self.mcp)

    @pytest.mark.asyncio
    async def test_empty_url(self, ctx):
        tool = self.mcp._tool_manager._tools["get_post_content"]
        result = await tool.fn(post_url="", ctx=ctx)
        assert result["error"] == "invalid_input"
        assert "cannot be empty" in result["message"]

    @pytest.mark.asyncio
    async def test_invalid_url(self, ctx):
        tool = self.mcp._tool_manager._tools["get_post_content"]
        result = await tool.fn(post_url="https://google.com/somepage", ctx=ctx)
        assert result["error"] == "invalid_input"

    @pytest.mark.asyncio
    async def test_profile_url_is_not_post(self, ctx):
        tool = self.mcp._tool_manager._tools["get_post_content"]
        result = await tool.fn(post_url="https://www.linkedin.com/in/johndoe/", ctx=ctx)
        assert result["error"] == "invalid_input"
