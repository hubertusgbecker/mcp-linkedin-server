"""
FastMCP server implementation for LinkedIn integration with tool registration.

Creates and configures the MCP server with comprehensive LinkedIn tool suite including
person profiles, company data, job information, and session management capabilities.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict

from fastmcp import FastMCP

from linkedin_mcp_server.drivers.browser import close_browser
from linkedin_mcp_server.tools.analytics import register_analytics_tools
from linkedin_mcp_server.tools.company import register_company_tools
from linkedin_mcp_server.tools.job import register_job_tools
from linkedin_mcp_server.tools.notifications import register_notification_tools
from linkedin_mcp_server.tools.person import register_person_tools
from linkedin_mcp_server.tools.post_content import register_post_content_tools

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastMCP) -> AsyncIterator[None]:
    """Manage server lifecycle - cleanup browser on shutdown."""
    logger.info("LinkedIn MCP Server starting...")
    yield
    logger.info("LinkedIn MCP Server shutting down...")
    await close_browser()


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP server with all LinkedIn tools."""
    mcp = FastMCP("linkedin_scraper", lifespan=lifespan)

    # Register all tools
    register_person_tools(mcp)
    register_company_tools(mcp)
    register_job_tools(mcp)
    register_analytics_tools(mcp)
    register_notification_tools(mcp)
    register_post_content_tools(mcp)

    # Register session management tool
    @mcp.tool()
    async def close_session() -> Dict[str, Any]:
        """
        Close the LinkedIn browser session and release all resources.

        Shuts down the Patchright browser instance, saves cookies for future
        sessions, and frees memory. Call this when you are done with all
        LinkedIn operations. The browser will be automatically re-launched
        on the next tool call if needed.

        Returns:
            Dict with:
            - status (str): "success" or "error"
            - message (str): Human-readable confirmation or error detail
        """
        try:
            await close_browser()
            return {
                "status": "success",
                "message": "Successfully closed the browser session and cleaned up resources",
            }
        except Exception as e:
            return {
                "status": "error",
                "message": f"Error closing browser session: {str(e)}",
            }

    return mcp
