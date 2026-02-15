"""
LinkedIn company profile scraping tools.

Provides MCP tools for extracting company information from LinkedIn
with comprehensive error handling.
"""

import logging
from typing import Any, Dict

from fastmcp import Context, FastMCP
from linkedin_scraper import CompanyPostsScraper, CompanyScraper
from mcp.types import ToolAnnotations

from mcp_linkedin_server.callbacks import MCPContextProgressCallback
from mcp_linkedin_server.drivers.browser import (
    ensure_authenticated,
    get_or_create_browser,
)
from mcp_linkedin_server.error_handler import handle_tool_error
from mcp_linkedin_server.utils.validation import validate_company_slug, validate_limit

logger = logging.getLogger(__name__)


def register_company_tools(mcp: FastMCP) -> None:
    """
    Register all company-related tools with the MCP server.

    Args:
        mcp: The MCP server instance
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Company Profile",
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def get_company_profile(company_name: str, ctx: Context) -> Dict[str, Any]:
        """
        Get a company's full LinkedIn profile by its URL slug.

        Scrapes the company's "About" page on LinkedIn for organizational details,
        employee highlights, and affiliated entities. Use this for company research,
        competitive analysis, or lead generation.

        Args:
            company_name: The URL slug that appears after linkedin.com/company/.
                Examples: "docker", "anthropic", "microsoft", "robert-bosch-gmbh".
                Do NOT pass full URLs — only the slug portion.

        Returns:
            Structured company data with the following fields:
            - linkedin_url (str): Full company page URL
            - name (str): Official company name as displayed on LinkedIn
            - about_us (str | null): Company description / "About" section
            - website (str | null): Company website URL
            - phone (str | null): Listed phone number
            - headquarters (str | null): HQ location (e.g. "Stuttgart, Baden-Württemberg")
            - founded (str | null): Year the company was founded
            - industry (str | null): Primary industry (e.g. "Motor Vehicle Manufacturing")
            - company_type (str | null): Organization type (e.g. "Public Company", "Nonprofit")
            - company_size (str | null): Employee range (e.g. "10,001+ employees")
            - specialties (str | null): Comma-separated list of specialties
            - headcount (int | null): Approximate employee count on LinkedIn
            - showcase_pages (list): Brand or product sub-pages, each with
              linkedin_url, name, and followers count
            - affiliated_companies (list): Sister companies or subsidiaries
            - employees (list): Featured employees, each with name, designation,
              and linkedin_url
        """
        try:
            # Validate input
            company_name = validate_company_slug(company_name)

            # Validate session before scraping
            await ensure_authenticated()

            # Construct LinkedIn URL from company name
            linkedin_url = f"https://www.linkedin.com/company/{company_name}/"

            logger.info(f"Scraping company: {linkedin_url}")

            browser = await get_or_create_browser()
            scraper = CompanyScraper(
                browser.page, callback=MCPContextProgressCallback(ctx)
            )
            company = await scraper.scrape(linkedin_url)

            return company.to_dict()

        except Exception as e:
            return handle_tool_error(e, "get_company_profile")

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Company Posts",
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def get_company_posts(
        company_name: str, ctx: Context, limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get recent posts from a company's LinkedIn feed.

        Scrapes the company's activity feed to retrieve their latest published
        content. Use this to analyze a company's content strategy, track
        announcements, or monitor engagement metrics.

        Args:
            company_name: The URL slug that appears after linkedin.com/company/.
                Examples: "docker", "anthropic", "microsoft".
                Do NOT pass full URLs — only the slug portion.
            limit: Maximum number of posts to retrieve. Default: 10.
                Higher values take longer as more scrolling is required.

        Returns:
            Dict with:
            - count (int): Number of posts actually returned (may be less than limit)
            - posts (list): List of post objects, each containing:
                - linkedin_url (str): Permalink to the post
                - urn (str): LinkedIn internal post identifier
                - text (str): Full post body text
                - posted_date (str | null): When the post was published (e.g. "2 weeks ago")
                - reactions_count (int): Total reactions (likes, celebrates, etc.)
                - comments_count (int): Number of comments on the post
                - reposts_count (int): Number of times the post was reposted
                - image_urls (list[str]): URLs of images attached to the post
                - video_url (str | null): Video URL if the post contains a video
                - article_url (str | null): URL of a linked article if present
        """
        try:
            # Validate input
            company_name = validate_company_slug(company_name)
            limit = validate_limit(limit, max_val=50)

            # Validate session before scraping
            await ensure_authenticated()

            # Construct LinkedIn URL from company name
            linkedin_url = f"https://www.linkedin.com/company/{company_name}/"

            logger.info(f"Scraping company posts: {linkedin_url} (limit: {limit})")

            browser = await get_or_create_browser()
            scraper = CompanyPostsScraper(
                browser.page, callback=MCPContextProgressCallback(ctx)
            )
            posts = await scraper.scrape(linkedin_url, limit=limit)

            return {"posts": [post.to_dict() for post in posts], "count": len(posts)}

        except Exception as e:
            return handle_tool_error(e, "get_company_posts")
