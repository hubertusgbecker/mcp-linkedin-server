"""
LinkedIn job scraping tools with search and detail extraction.

Provides MCP tools for job posting details and job searches
with comprehensive filtering and structured data extraction.
"""

import logging
from typing import Any, Dict

from fastmcp import Context, FastMCP
from linkedin_scraper import JobScraper, JobSearchScraper
from mcp.types import ToolAnnotations

from mcp_linkedin_server.callbacks import MCPContextProgressCallback
from mcp_linkedin_server.drivers.browser import (
    ensure_authenticated,
    get_or_create_browser,
)
from mcp_linkedin_server.error_handler import handle_tool_error

logger = logging.getLogger(__name__)


def register_job_tools(mcp: FastMCP) -> None:
    """
    Register all job-related tools with the MCP server.

    Args:
        mcp: The MCP server instance
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Job Details",
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def get_job_details(job_id: str, ctx: Context) -> Dict[str, Any]:
        """
        Get full details of a specific LinkedIn job posting.

        Scrapes a single job listing page for its complete description, requirements,
        and metadata. Use search_jobs first to find job IDs, then call this for details.

        Args:
            job_id: The numeric LinkedIn job ID. This appears in job URLs as
                linkedin.com/jobs/view/{job_id}/.
                Examples: "4252026496", "3856789012".
                You can obtain job IDs from the search_jobs tool.

        Returns:
            Structured job data with the following fields:
            - title (str): Job title (e.g. "Senior Software Engineer")
            - company (str): Hiring company name
            - location (str | null): Job location (e.g. "Stuttgart, Germany (On-site)")
            - posted_date (str | null): When the job was posted (e.g. "2 weeks ago")
            - applicants (str | null): Number of applicants (e.g. "Over 100 applicants")
            - job_description (str): Full job description text including responsibilities,
              requirements, and qualifications
            - seniority_level (str | null): e.g. "Mid-Senior level"
            - employment_type (str | null): e.g. "Full-time", "Contract"
            - job_function (str | null): e.g. "Engineering", "Information Technology"
            - industries (str | null): e.g. "Software Development"
            - linkedin_url (str): Direct link to the job posting
            - benefits (list): Listed job benefits if available
        """
        try:
            # Validate session before scraping
            await ensure_authenticated()

            # Construct LinkedIn URL from job ID
            job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

            logger.info(f"Scraping job: {job_url}")

            browser = await get_or_create_browser()
            scraper = JobScraper(browser.page, callback=MCPContextProgressCallback(ctx))
            job = await scraper.scrape(job_url)

            return job.to_dict()

        except Exception as e:
            return handle_tool_error(e, "get_job_details")

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Search Jobs",
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def search_jobs(
        keywords: str,
        ctx: Context,
        location: str | None = None,
        limit: int = 25,
    ) -> Dict[str, Any]:
        """
        Search for job postings on LinkedIn by keywords and location.

        Returns a list of job URLs matching the search criteria. This is a
        discovery tool — it returns URLs only. To get full job details
        (title, description, requirements), pass each URL's job ID to
        the get_job_details tool.

        Args:
            keywords: Search query for job titles or skills.
                Examples: "software engineer", "data scientist python",
                "product manager AI".
            location: Optional geographic filter. Can be a city, country, or "Remote".
                Examples: "San Francisco", "Germany", "Remote".
                If omitted, searches globally.
            limit: Maximum number of job URLs to return. Default: 25.
                LinkedIn may return fewer results depending on the query.

        Returns:
            Dict with:
            - job_urls (list[str]): LinkedIn job posting URLs. Extract the numeric
              job ID from each URL (the number after /jobs/view/) to use with
              get_job_details.
            - count (int): Number of job URLs returned.
        """
        try:
            # Validate session before scraping
            await ensure_authenticated()

            logger.info(f"Searching jobs: keywords='{keywords}', location='{location}'")

            browser = await get_or_create_browser()
            scraper = JobSearchScraper(
                browser.page, callback=MCPContextProgressCallback(ctx)
            )
            job_urls = await scraper.search(
                keywords=keywords,
                location=location,
                limit=limit,
            )

            return {"job_urls": job_urls, "count": len(job_urls)}

        except Exception as e:
            return handle_tool_error(e, "search_jobs")
