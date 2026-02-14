"""
LinkedIn post content scraping tool.

Provides an MCP tool for extracting the full content of a LinkedIn post
given its URL. Designed to complement get_notifications, which returns
truncated post previews alongside post_url links.
"""

import asyncio
import logging
import re
from typing import Any, Dict, Optional

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from linkedin_mcp_server.drivers.browser import (
    ensure_authenticated,
    get_or_create_browser,
)
from linkedin_mcp_server.error_handler import handle_tool_error

logger = logging.getLogger(__name__)


def _parse_engagement_count(text: Optional[str]) -> Optional[int]:
    """Parse an engagement label like '142 reactions' or '1.2K comments' to int.

    Handles:
    - Plain numbers: '142', '3'
    - Numbers with commas: '1,823'
    - K/M suffixes: '1.2K', '2.5M'
    - Labels: '142 reactions', '23 comments', '8 reposts'

    Returns None for None, empty, or unparseable strings.
    """
    if not text:
        return None

    text = text.strip()
    if not text:
        return None

    # Extract leading number (possibly with commas, decimal, K/M suffix)
    match = re.match(r"^([\d,]+\.?\d*)\s*([KkMm])?", text)
    if not match:
        return None

    num_str = match.group(1).replace(",", "")
    suffix = (match.group(2) or "").upper()

    try:
        value = float(num_str)
    except ValueError:
        return None

    if suffix == "K":
        value *= 1000
    elif suffix == "M":
        value *= 1_000_000

    return int(value)


_POST_CONTENT_JS = r"""() => {
    const result = {
        text: '',
        author: '',
        headline: '',
        time_raw: '',
        reactions_label: '',
        comments_label: '',
        reposts_label: '',
        author_profile_url: '',
    };

    // Post text
    const textSelectors = [
        '.feed-shared-update-v2__description',
        '.feed-shared-inline-show-more-text',
        '.update-components-text',
        '[data-ad-preview="message"]',
    ];
    for (const sel of textSelectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.trim()) {
            result.text = el.innerText.trim();
            break;
        }
    }

    // Author name
    const authorSelectors = [
        '.update-components-actor__title .visually-hidden',
        '.update-components-actor__name .visually-hidden',
        '.update-components-actor__name',
    ];
    for (const sel of authorSelectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.trim()) {
            result.author = el.innerText.trim();
            break;
        }
    }

    // Author headline
    const headlineSelectors = [
        '.update-components-actor__description .visually-hidden',
        '.update-components-actor__description',
    ];
    for (const sel of headlineSelectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.trim()) {
            result.headline = el.innerText.trim();
            break;
        }
    }

    // Author profile link (person or company)
    const actorContainer = document.querySelector('.update-components-actor__container')
        || document.querySelector('[class*="update-components-actor"]');
    if (actorContainer) {
        const personLink = actorContainer.querySelector('a[href*="/in/"]');
        if (personLink) {
            const href = personLink.getAttribute('href') || '';
            const m = href.match(/\/in\/([^/?#]+)/);
            if (m) result.author_profile_url = '/in/' + decodeURIComponent(m[1]);
        } else {
            const companyLink = actorContainer.querySelector('a[href*="/company/"]');
            if (companyLink) {
                const href = companyLink.getAttribute('href') || '';
                const m = href.match(/\/company\/([^/?#]+)/);
                if (m) result.author_profile_url = '/company/' + decodeURIComponent(m[1]);
            }
        }
    }

    // Posted time
    const timeSelectors = [
        '.update-components-actor__sub-description .visually-hidden',
        '.update-components-actor__sub-description',
    ];
    for (const sel of timeSelectors) {
        const el = document.querySelector(sel);
        if (el && el.innerText.trim()) {
            result.time_raw = el.innerText.trim();
            break;
        }
    }

    // Reactions count from button aria-label
    const reactionBtn = document.querySelector('button[aria-label*="reaction"]');
    if (reactionBtn) {
        result.reactions_label = reactionBtn.getAttribute('aria-label') || '';
    }

    // Comments count - look for button with aria-label containing "comment"
    // but not the "Comment" action button
    const allBtns = document.querySelectorAll('button[aria-label]');
    for (const btn of allBtns) {
        const label = btn.getAttribute('aria-label') || '';
        if (/^\d/.test(label) && /comment/i.test(label)) {
            result.comments_label = label;
            break;
        }
    }

    // Reposts count
    for (const btn of allBtns) {
        const label = btn.getAttribute('aria-label') || '';
        if (/^\d/.test(label) && /repost/i.test(label)) {
            result.reposts_label = label;
            break;
        }
    }

    return result;
}"""


def _parse_username_from_profile_url(url: str) -> Optional[str]:
    """Extract LinkedIn username from a profile URL fragment.

    Handles /in/<username> and /company/<slug> patterns.
    Returns None for empty or unrecognised strings.
    """
    if not url:
        return None
    match = re.match(r"^/(?:in|company)/([^/?#]+)", url)
    return match.group(1) if match else None


async def _extract_post_content_from_page(page: Any) -> Dict[str, Any]:
    """Extract full post content from a LinkedIn post page.

    Args:
        page: Patchright page object (already navigated to a post URL).

    Returns:
        Dict with text, author, author_headline, posted_ago,
        reactions_count, comments_count, reposts_count.
    """
    try:
        raw = await page.evaluate(_POST_CONTENT_JS)
    except Exception:
        logger.debug("Failed to extract post content from DOM", exc_info=True)
        raw = {}

    text = raw.get("text", "")
    author = raw.get("author", "")
    headline = raw.get("headline", "")
    time_raw = raw.get("time_raw", "")

    # Strip visibility suffix from time: "3 minutes ago * Visible to anyone..."
    posted_ago = time_raw
    if "\u2022" in time_raw:
        posted_ago = time_raw.split("\u2022")[0].strip()

    return {
        "text": text,
        "author": author,
        "linkedin_username": _parse_username_from_profile_url(
            raw.get("author_profile_url", "")
        ),
        "author_headline": headline,
        "posted_ago": posted_ago,
        "reactions_count": _parse_engagement_count(raw.get("reactions_label", "")),
        "comments_count": _parse_engagement_count(raw.get("comments_label", "")),
        "reposts_count": _parse_engagement_count(raw.get("reposts_label", "")),
    }


def register_post_content_tools(mcp: FastMCP) -> None:
    """Register post content tools with the MCP server.

    Args:
        mcp: The MCP server instance
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Post Content",
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=True,
        )
    )
    async def get_post_content(post_url: str, ctx: Context) -> Dict[str, Any]:
        """
        Get the full content of a LinkedIn post by its URL.

        Navigates to a LinkedIn post page and extracts the complete post text,
        author information, and engagement metrics. Use this after get_notifications
        to retrieve the full text of posts that were truncated in the notification
        preview, or to get details on any LinkedIn post by URL.

        Args:
            post_url: Full LinkedIn post URL. Accepted formats:
                - https://www.linkedin.com/feed/update/urn:li:activity:XXXX/
                - https://www.linkedin.com/posts/username_slug-XXXX/
                - A post_url value returned by get_notifications

        Returns:
            Dict with:
            - post_url (str): The URL that was scraped
            - text (str): Full post body text (not truncated)
            - author (str): Name of the post author
            - linkedin_username (str | null): LinkedIn username or company slug extracted
              from the author profile link (e.g. "gennarocuofano", "nvidia").
              null when no profile link is found.
            - author_headline (str): Author's LinkedIn headline
            - posted_ago (str): Relative timestamp (e.g. "3 minutes ago", "2 hours ago")
            - reactions_count (int | null): Number of reactions, null if not available
            - comments_count (int | null): Number of comments, null if not available
            - reposts_count (int | null): Number of reposts, null if not available
        """
        try:
            await ensure_authenticated()

            logger.info(f"Scraping post content: {post_url}")

            browser = await get_or_create_browser()
            page = browser.page

            await ctx.report_progress(
                progress=10, total=100, message="Navigating to post"
            )

            await page.goto(
                post_url,
                wait_until="domcontentloaded",
                timeout=30000,
            )

            try:
                await page.wait_for_selector("main", timeout=15000)
            except Exception:
                logger.warning("Timeout waiting for <main> element on post page")

            # Wait for content to render
            await asyncio.sleep(3)

            await ctx.report_progress(
                progress=50, total=100, message="Extracting post content"
            )

            content = await _extract_post_content_from_page(page)
            content["post_url"] = post_url

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return content

        except Exception as e:
            return handle_tool_error(e, "get_post_content")
