"""
LinkedIn person profile scraping tools.

Provides MCP tools for extracting comprehensive LinkedIn profile information including
experience, education, interests, accomplishments, and contact details.

Falls back to direct page text extraction when the scraper's CSS selectors are outdated.
"""

import asyncio
import logging
import re
from typing import Any, Dict

from fastmcp import Context, FastMCP
from linkedin_scraper import PersonScraper
from mcp.types import ToolAnnotations

from linkedin_mcp_server.callbacks import MCPContextProgressCallback
from linkedin_mcp_server.drivers.browser import (
    ensure_authenticated,
    get_or_create_browser,
)
from linkedin_mcp_server.error_handler import handle_tool_error

logger = logging.getLogger(__name__)


def _is_empty_result(result: Dict[str, Any]) -> bool:
    """Check if a scraper result is effectively empty."""
    name = result.get("name", "Unknown")
    if name and name != "Unknown":
        return False
    return True


async def _extract_profile_from_page_text(page, linkedin_url: str) -> Dict[str, Any]:
    """
    Fallback: extract profile data directly from page innerText.

    When the PersonScraper's CSS selectors are outdated, this parses the
    visible text content of the profile page instead.
    """
    await page.goto(linkedin_url, wait_until="domcontentloaded")
    await asyncio.sleep(4)

    # Get the page title for the name
    title = await page.title()
    name_match = re.match(r"^(.+?)\s*[|·]", title)
    name = name_match.group(1).strip() if name_match else title.strip()

    # Get the full text of the main element
    main_text = await page.evaluate(
        "() => { const m = document.querySelector('main'); return m ? m.innerText : ''; }"
    )

    lines = [line.strip() for line in main_text.split("\n") if line.strip()]

    # Parse the top card (first few lines)
    location = None
    about = None
    headline = None

    # Find the name line and extract nearby info
    name_idx = None
    for i, line in enumerate(lines):
        if name and name in line and len(line) < len(name) + 20:
            name_idx = i
            break

    if name_idx is not None:
        # Lines after name: possible pronoun, headline, location
        remaining = lines[name_idx + 1 :]
        for line in remaining[:5]:
            if line.lower() in (
                "he/him",
                "she/her",
                "they/them",
                "he/they",
                "she/they",
            ):
                continue
            if not headline:
                headline = line
                continue
            # Location usually contains a comma or "Area"
            if not location and (
                "," in line or "Germany" in line or "Area" in line or "United" in line
            ):
                location = line
                break

    # Extract About section
    about_marker = None
    for i, line in enumerate(lines):
        if line == "About":
            about_marker = i
            break

    if about_marker is not None:
        about_lines = []
        for line in lines[about_marker + 1 :]:
            if line in ("Activity", "Experience", "Education", "Show all", "… more"):
                break
            if line.startswith("Analytics") or line.startswith("Private to you"):
                break
            about_lines.append(line)
        if about_lines:
            about = " ".join(about_lines)

    # Extract Experience section
    experiences = []
    exp_marker = None
    for i, line in enumerate(lines):
        if line == "Experience":
            exp_marker = i
            break

    if exp_marker is not None:
        exp_lines = lines[exp_marker + 1 :]
        # Experience entries end at next section
        exp_block = []
        for line in exp_lines:
            if line in (
                "Education",
                "Licenses & certifications",
                "Skills",
                "Interests",
                "Recommendations",
                "Activity",
            ):
                break
            if line in ("Show all experiences", "Show all"):
                break
            exp_block.append(line)

        # Parse experience entries - they come in groups
        # Typical pattern: Title, Company · Type, Date range · Duration, Location
        i = 0
        while i < len(exp_block):
            line = exp_block[i]
            # Skip navigation/UI elements
            if line in ("logo", "") or line.startswith("Show all"):
                i += 1
                continue

            # Try to detect an experience entry
            # Usually: position, then "Company · Type", then date/duration, then location
            position_title = line
            company = ""
            date_range = ""
            loc = ""
            desc = ""

            if i + 1 < len(exp_block):
                next_line = exp_block[i + 1]
                if (
                    "·" in next_line
                    or "Full-time" in next_line
                    or "Part-time" in next_line
                    or "Contract" in next_line
                    or "Self-employed" in next_line
                ):
                    company = next_line.split("·")[0].strip()
                    i += 1
                elif not any(c.isdigit() for c in next_line):
                    company = next_line
                    i += 1

            if i + 1 < len(exp_block):
                next_line = exp_block[i + 1]
                if any(
                    month in next_line
                    for month in [
                        "Jan",
                        "Feb",
                        "Mar",
                        "Apr",
                        "May",
                        "Jun",
                        "Jul",
                        "Aug",
                        "Sep",
                        "Oct",
                        "Nov",
                        "Dec",
                        "Present",
                    ]
                ) or re.search(r"\d{4}\s*-", next_line):
                    date_range = next_line
                    i += 1

            if i + 1 < len(exp_block):
                next_line = exp_block[i + 1]
                if "," in next_line and any(
                    geo in next_line
                    for geo in [
                        "Germany",
                        "United",
                        "Remote",
                        "Area",
                        "France",
                        "India",
                        "China",
                        "UK",
                        "Japan",
                    ]
                ):
                    loc = next_line
                    i += 1

            if position_title and (company or date_range):
                from_date, to_date, duration = _parse_date_range(date_range)
                experiences.append(
                    {
                        "position_title": position_title,
                        "institution_name": company,
                        "linkedin_url": None,
                        "from_date": from_date,
                        "to_date": to_date,
                        "duration": duration,
                        "location": loc or None,
                        "description": desc or None,
                    }
                )

            i += 1

    # Extract Education section
    educations = []
    edu_marker = None
    for i, line in enumerate(lines):
        if line == "Education":
            edu_marker = i
            break

    if edu_marker is not None:
        edu_lines = lines[edu_marker + 1 :]
        edu_block = []
        for line in edu_lines:
            if line in (
                "Licenses & certifications",
                "Skills",
                "Interests",
                "Experience",
                "Recommendations",
                "Activity",
            ):
                break
            if line in ("Show all education", "Show all"):
                break
            edu_block.append(line)

        i = 0
        while i < len(edu_block):
            line = edu_block[i]
            if line in ("logo", ""):
                i += 1
                continue

            institution = line
            degree = None
            dates = ""

            if i + 1 < len(edu_block):
                next_line = edu_block[i + 1]
                if not re.search(r"\d{4}\s*-\s*\d{4}", next_line):
                    degree = next_line
                    i += 1

            if i + 1 < len(edu_block):
                next_line = edu_block[i + 1]
                if re.search(r"\d{4}", next_line):
                    dates = next_line
                    i += 1

            from_date, to_date = None, None
            if " - " in dates:
                parts = dates.split(" - ")
                from_date = parts[0].strip()
                to_date = parts[1].strip() if len(parts) > 1 else None

            if institution:
                educations.append(
                    {
                        "institution_name": institution,
                        "degree": degree,
                        "linkedin_url": None,
                        "from_date": from_date,
                        "to_date": to_date,
                        "description": None,
                    }
                )

            i += 1

    # Parse headline for company/job_title
    company_name = None
    job_title = None
    if headline:
        if " at " in headline:
            parts = headline.split(" at ", 1)
            job_title = parts[0].strip()
            company_name = parts[1].split("|")[0].strip()
        elif "|" in headline:
            job_title = headline.split("|")[0].strip()

    return {
        "linkedin_url": linkedin_url,
        "name": name,
        "location": location,
        "about": about,
        "open_to_work": any("open to" in line.lower() for line in lines[:20]),
        "experiences": experiences,
        "educations": educations,
        "interests": [],
        "accomplishments": [],
        "contacts": [],
        "company": company_name,
        "job_title": job_title,
    }


def _parse_date_range(date_str: str):
    """Parse a date range string like 'Jan 2020 - Present · 5 yrs'."""
    if not date_str:
        return None, None, None
    parts = date_str.split("·")
    times = parts[0].strip() if parts else ""
    duration = parts[1].strip() if len(parts) > 1 else None
    if " - " in times:
        dp = times.split(" - ")
        return dp[0].strip(), dp[1].strip() if len(dp) > 1 else None, duration
    return times, None, duration


def register_person_tools(mcp: FastMCP) -> None:
    """
    Register all person-related tools with the MCP server.

    Args:
        mcp: The MCP server instance
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Person Profile",
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def get_person_profile(
        linkedin_username: str, ctx: Context
    ) -> Dict[str, Any]:
        """
        Get a specific person's LinkedIn profile.

        Args:
            linkedin_username: LinkedIn username (e.g., "stickerdaniel", "williamhgates")
            ctx: FastMCP context for progress reporting

        Returns:
            Structured data from the person's profile including:
            - linkedin_url, name, location, about, open_to_work
            - experiences: List of work history (position_title, institution_name,
              linkedin_url, from_date, to_date, duration, location, description)
            - educations: List of education (institution_name, degree, linkedin_url,
              from_date, to_date, description)
            - interests: List of interests with category (company, group, school,
              newsletter, influencer) and linkedin_url
            - accomplishments: List of accomplishments (category, title)
            - contacts: List of contact info (type: email/phone/website/linkedin/
              twitter/birthday/address, value, label)
        """
        try:
            # Validate session before scraping
            await ensure_authenticated()

            # Construct LinkedIn URL from username
            linkedin_url = f"https://www.linkedin.com/in/{linkedin_username}/"

            logger.info(f"Scraping profile: {linkedin_url}")

            browser = await get_or_create_browser()

            # Try the structured scraper first
            try:
                scraper = PersonScraper(
                    browser.page, callback=MCPContextProgressCallback(ctx)
                )
                person = await scraper.scrape(linkedin_url)
                result = person.to_dict()

                if not _is_empty_result(result):
                    return result

                logger.info(
                    "Scraper returned empty result, falling back to text extraction"
                )
            except Exception as scraper_err:
                logger.info(
                    f"Scraper failed ({scraper_err}), falling back to text extraction"
                )

            # Fallback: extract from page text directly
            await ctx.report_progress(progress=50, total=100)
            result = await _extract_profile_from_page_text(browser.page, linkedin_url)
            await ctx.report_progress(progress=100, total=100)
            return result

        except Exception as e:
            return handle_tool_error(e, "get_person_profile")
