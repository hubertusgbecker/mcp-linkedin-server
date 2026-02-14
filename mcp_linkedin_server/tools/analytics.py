"""
LinkedIn profile analytics scraping tool.

Provides an MCP tool for extracting dashboard analytics from the logged-in
user's own LinkedIn profile: profile views, post impressions, search appearances,
followers, and weekly sharing activity.
"""

import asyncio
import logging
import re
from typing import Any, Dict, Optional

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from mcp_linkedin_server.drivers.browser import (
    ensure_authenticated,
    get_or_create_browser,
)
from mcp_linkedin_server.error_handler import handle_tool_error

logger = logging.getLogger(__name__)


def _parse_analytics_number(text: Optional[str]) -> Optional[int]:
    """Parse a display number like '142', '1,823', '1.2K', '2.5M' into an int.

    Returns None for None, empty strings, or unparseable values like '--'.
    """
    if text is None:
        return None
    text = text.strip()
    if not text or text == "--":
        return None

    # Handle K/M suffixes
    text_upper = text.upper()
    multiplier = 1
    if text_upper.endswith("K"):
        multiplier = 1000
        text_upper = text_upper[:-1]
    elif text_upper.endswith("M"):
        multiplier = 1_000_000
        text_upper = text_upper[:-1]

    # Remove commas
    text_upper = text_upper.replace(",", "")

    try:
        return int(float(text_upper) * multiplier)
    except (ValueError, TypeError):
        return None


async def _extract_analytics_from_page(page) -> Dict[str, Any]:
    """Extract analytics metrics from the LinkedIn dashboard page's innerText.

    The dashboard at linkedin.com/dashboard/ presents metrics in a two-line
    format where the number appears on one line and the label on the next:

        58
        Post impressions

        2,517
        Followers

        615
        Profile viewers

        39
        Search appearances

    Weekly activity appears as:
        0 posts
        3 comments
    """
    # Get the full text of the main element
    main_text = await page.evaluate(
        "() => { const m = document.querySelector('main'); return m ? m.innerText : ''; }"
    )

    logger.debug(f"Analytics main text length: {len(main_text)}")
    logger.debug(f"Analytics main text (first 3000 chars): {main_text[:3000]}")

    # Fall back to body text if main is empty
    if not main_text:
        main_text = await page.evaluate("() => document.body.innerText || ''")
        logger.debug(f"Falling back to body text, length: {len(main_text)}")

    lines = [line.strip() for line in main_text.split("\n") if line.strip()]

    result: Dict[str, Any] = {
        "profile_views": None,
        "post_impressions": None,
        "search_appearances": None,
        "followers": None,
        "weekly_posts": None,
        "weekly_comments": None,
    }

    # Dashboard uses a two-line format: number on one line, label on the next.
    # Scan pairs of consecutive lines.
    for i, line in enumerate(lines):
        line_lower = line.lower()
        prev = lines[i - 1] if i > 0 else ""

        # Check if current line is a label and previous line is the number
        if "post impression" in line_lower:
            result["post_impressions"] = _parse_analytics_number(prev)
        elif "profile viewer" in line_lower:
            result["profile_views"] = _parse_analytics_number(prev)
        elif "search appearance" in line_lower:
            result["search_appearances"] = _parse_analytics_number(prev)
        elif line_lower == "followers" or re.match(r"^followers?\b", line_lower):
            result["followers"] = _parse_analytics_number(prev)

        # Weekly sharing: "0 posts", "3 comments" (single-line format)
        posts_match = re.match(r"^(\d+)\s+posts?$", line_lower)
        if posts_match:
            result["weekly_posts"] = int(posts_match.group(1))

        comments_match = re.match(r"^(\d+)\s+comments?$", line_lower)
        if comments_match:
            result["weekly_comments"] = int(comments_match.group(1))

    return result


def register_analytics_tools(mcp: FastMCP) -> None:
    """Register profile analytics tools with the MCP server.

    Args:
        mcp: The MCP server instance
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Profile Analytics",
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=False,
        )
    )
    async def get_profile_analytics(ctx: Context) -> Dict[str, Any]:
        """
        Get analytics from the logged-in user's LinkedIn dashboard.

        Scrapes linkedin.com/dashboard/ for the authenticated user's own analytics.
        No parameters needed — this always returns data for the currently logged-in account.
        Use this to monitor profile performance, audience growth, and content engagement.

        Returns:
            Structured analytics data with the following fields:
            - profile_views (int | null): Total number of unique LinkedIn members
              who visited the authenticated user's profile. Covers the past 90 days.
            - post_impressions (int | null): The number of times the user's posts
              were displayed on screen across LinkedIn feeds. Covers the past 7 days.
            - search_appearances (int | null): How many times the user's profile
              appeared in LinkedIn search results. Covers the previous week.
            - followers (int | null): Total number of people currently following
              the user, including both connections and non-connection followers.
            - weekly_posts (int | null): Number of posts the user published in
              the current week (Mon–Sun). Part of LinkedIn's weekly sharing tracker.
            - weekly_comments (int | null): Number of comments the user made in
              the current week (Mon–Sun). Part of LinkedIn's weekly sharing tracker.

            Any field may be null if the metric is unavailable or the page layout changed.
        """
        try:
            await ensure_authenticated()

            logger.info("Scraping own profile analytics dashboard")

            browser = await get_or_create_browser()
            page = browser.page

            # Navigate to the LinkedIn analytics dashboard
            await ctx.report_progress(
                progress=10, total=100, message="Navigating to dashboard"
            )

            await page.goto(
                "https://www.linkedin.com/dashboard/",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            logger.debug(f"Current URL after navigation: {page.url}")

            # Wait for dashboard content to render
            try:
                await page.wait_for_selector("main", timeout=15000)
            except Exception:
                logger.warning("Timeout waiting for <main> element")

            # Extra time for dynamic content to render
            await asyncio.sleep(3)

            # Extract analytics from the dashboard section
            await ctx.report_progress(
                progress=50, total=100, message="Extracting analytics"
            )
            result = await _extract_analytics_from_page(page)

            await ctx.report_progress(progress=100, total=100, message="Complete")
            return result

        except Exception as e:
            return handle_tool_error(e, "get_profile_analytics")
