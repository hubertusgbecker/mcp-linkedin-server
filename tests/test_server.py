"""Tests for server.py: MCP server creation and tool registration."""

from unittest.mock import AsyncMock, patch


from linkedin_mcp_server.server import create_mcp_server


class TestCreateMCPServer:
    def test_creates_server_instance(self):
        mcp = create_mcp_server()
        assert mcp is not None
        assert mcp.name == "linkedin_scraper"

    async def test_all_tools_registered(self):
        mcp = create_mcp_server()
        tools = await mcp.get_tools()
        # get_tools() returns a dict keyed by tool name
        tool_names = (
            set(tools.keys())
            if isinstance(tools, dict)
            else {t if isinstance(t, str) else t.name for t in tools}
        )

        expected = {
            "get_person_profile",
            "get_company_profile",
            "get_company_posts",
            "get_job_details",
            "search_jobs",
            "get_profile_analytics",
            "close_session",
        }
        assert expected == tool_names

    async def test_close_session_success(self):
        mcp = create_mcp_server()
        tool = await mcp.get_tool("close_session")

        with patch(
            "linkedin_mcp_server.server.close_browser",
            new_callable=AsyncMock,
        ):
            result = await tool.fn()

        assert result["status"] == "success"
        assert "closed" in result["message"].lower()

    async def test_close_session_error(self):
        mcp = create_mcp_server()
        tool = await mcp.get_tool("close_session")

        with patch(
            "linkedin_mcp_server.server.close_browser",
            new_callable=AsyncMock,
            side_effect=RuntimeError("browser already closed"),
        ):
            result = await tool.fn()

        assert result["status"] == "error"
        assert "browser already closed" in result["message"]


class TestLifespan:
    async def test_lifespan_calls_close_browser(self):
        """Lifespan context manager closes browser on exit."""
        from linkedin_mcp_server.server import lifespan

        mcp = create_mcp_server()

        with patch(
            "linkedin_mcp_server.server.close_browser",
            new_callable=AsyncMock,
        ) as mock_close:
            async with lifespan(mcp):
                pass  # server "runs"

            mock_close.assert_awaited_once()
