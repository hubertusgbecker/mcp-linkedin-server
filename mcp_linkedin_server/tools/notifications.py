"""
LinkedIn notifications scraping tool.

Provides an MCP tool for extracting recent notifications from the logged-in
user's LinkedIn notifications page (linkedin.com/notifications/).
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from mcp_linkedin_server.drivers.browser import (
    ensure_authenticated,
    get_or_create_browser,
)
from mcp_linkedin_server.error_handler import handle_tool_error

logger = logging.getLogger(__name__)

# Lines that are navigation tabs or UI chrome, not notifications
_SKIP_LINES = frozenset(
    {
        "all",
        "jobs",
        "my posts",
        "mentions",
        "new notifications",
        "earlier",
        "show more results",
        "no notifications yet.",
    }
)

# Regex for relative time stamps: "5m", "33m", "1h", "14h", "2d", "1w", "19s"
_TIME_AGO_RE = re.compile(r"^(\d+)\s*(s|m|h|d|w)$", re.IGNORECASE)

# Multipliers to convert time units to minutes
_TIME_MULTIPLIERS = {"s": 0, "m": 1, "h": 60, "d": 1440, "w": 10080}


def _parse_time_ago(text: Optional[str]) -> Optional[int]:
    """Convert a relative timestamp like '5m', '1h', '2d' to minutes.

    Returns None for None, empty, or unrecognisable strings.
    Seconds are rounded down to 0 minutes.
    """
    if not text:
        return None
    match = _TIME_AGO_RE.match(text.strip())
    if not match:
        return None
    value = int(match.group(1))
    unit = match.group(2).lower()
    return value * _TIME_MULTIPLIERS[unit]


# Patterns for notification content lines
# "Author posted: text..."
# "Author reposted Author's post: text..."
# "Author commented on your post: text..."
# "Author liked your post"
# "Author hosted this event. Watch the recording."
# "Author and N others liked your post"
_NOTIFICATION_PATTERNS = [
    # reposted (must come before generic "posted")
    re.compile(
        r"^(?P<author>.+?)\s+reposted\s+.+?(?:'s post|'s comment)?:\s*(?P<text>.+)$",
        re.DOTALL,
    ),
    # posted
    re.compile(
        r"^(?P<author>.+?)\s+posted:\s*(?P<text>.+)$",
        re.DOTALL,
    ),
    # commented on
    re.compile(
        r"^(?P<author>.+?)\s+(?P<action_full>commented on (?:your post|a post)):\s*(?P<text>.+)$",
        re.DOTALL,
    ),
    # liked / reacted
    re.compile(
        r"^(?P<author>.+?)\s+(?P<action_full>liked your (?:post|comment|article)|reacted to your (?:post|comment))(?:\s*(?P<text>.*))?$",
        re.DOTALL,
    ),
    # event hosted
    re.compile(
        r"^(?P<author>.+?)\s+hosted this event\..*$",
        re.DOTALL,
    ),
    # generic "Author verb: text" fallback
    re.compile(
        r"^(?P<author>.+?)\s+(?P<action_full>shared|mentioned you|sent you a message|viewed your profile|accepted your invitation|is now following you)(?::\s*(?P<text>.+))?$",
        re.DOTALL,
    ),
]


def _parse_notification_line(line: str) -> Optional[Dict[str, str]]:
    """Parse a single notification content line into author, action, and text.

    Returns None for non-notification lines (tabs, status, empty).
    """
    if not line:
        return None

    stripped = line.strip()
    if not stripped:
        return None

    # Skip UI chrome and status lines
    if stripped.lower() in _SKIP_LINES:
        return None
    if stripped.lower().startswith("status is "):
        return None
    if stripped.lower().startswith("unread notification"):
        return None

    # Skip time-only lines
    if _TIME_AGO_RE.match(stripped):
        return None

    # Skip attendee/comment count lines like "109 Attendees • 46 Comments"
    if re.match(
        r"^\d+\s+Attendees?\s*[•·]\s*\d+\s+Comments?$", stripped, re.IGNORECASE
    ):
        return None

    # Try each pattern
    for pattern in _NOTIFICATION_PATTERNS:
        match = pattern.match(stripped)
        if match:
            groups = match.groupdict()
            author = groups.get("author", "").strip()
            text = groups.get("text", "").strip() if groups.get("text") else ""

            # Determine action from the pattern
            if "reposted" in pattern.pattern:
                action = "reposted"
            elif "posted:" in pattern.pattern:
                action = "posted"
            elif "hosted this event" in pattern.pattern:
                action = "hosted this event"
            elif "action_full" in groups and groups["action_full"]:
                action = groups["action_full"]
            else:
                action = "unknown"

            return {"author": author, "action": action, "text": text}

    return None


_PROFILE_LINKS_JS = r"""() => {
    const result = [];
    const main = document.querySelector('main') || document.body;
    const links = main.querySelectorAll('a[href*="/in/"], a[href*="/company/"]');
    for (const a of links) {
        const href = a.getAttribute('href') || '';
        const personMatch = href.match(/\/in\/([^/?#]+)/);
        const companyMatch = href.match(/\/company\/([^/?#]+)/);
        const username = personMatch
            ? decodeURIComponent(personMatch[1])
            : companyMatch
              ? decodeURIComponent(companyMatch[1])
              : null;
        if (!username) continue;

        // LinkedIn notification profile links are avatar images whose
        // textContent is a status string ("Status is offline") and whose
        // aria-label carries the name: "View Ethan Mollick\u2019s profile."
        const aria = (a.getAttribute('aria-label') || '').trim();
        let name = '';
        if (aria) {
            // Strip "View " prefix and remove possessive + " profile." suffix.
            // The apostrophe may be U+0027 ('), U+2018, or U+2019.
            name = aria
                .replace(/^View\s+/i, '')
                .replace(/[\u0027\u2018\u2019]s\s+profile\.?\s*$/i, '')
                .trim();
            // If stripping didn't change anything, discard
            if (name === aria) name = '';
        }
        // Fallback: try innerText if aria-label didn't work
        if (!name) {
            const txt = (a.innerText || '').trim();
            if (txt && !txt.startsWith('Status is ')) {
                name = txt;
            }
        }
        if (name) {
            result.push({name, username});
        }
    }
    return result;
}"""


_POST_URLS_JS = r"""() => {
    const cards = document.querySelectorAll('article.nt-card, div.nt-card');
    const urls = [];
    for (const card of cards) {
        const link = card.querySelector('a.nt-card__headline');
        if (link) {
            const href = link.getAttribute('href') || '';
            const urnMatch = href.match(/highlightedUpdateUrn=urn%3Ali%3Aactivity%3A(\d+)/);
            if (urnMatch) {
                urls.push('https://www.linkedin.com/feed/update/urn:li:activity:' + urnMatch[1] + '/');
            } else {
                urls.push(null);
            }
        } else {
            urls.push(null);
        }
    }
    return urls;
}"""


async def _extract_post_urls(page: Any) -> List[Optional[str]]:
    """Extract an ordered list of post URLs from notification card headline links.

    Each notification card has a headline link with a ``highlightedUpdateUrn``
    query parameter. This function extracts those URNs and converts them to
    canonical post URLs.

    Returns:
        A list of post URLs (one per card, in DOM order). Entries are None
        for cards without a recognisable post link.
    """
    try:
        return await page.evaluate(_POST_URLS_JS)
    except Exception:
        logger.debug("Failed to extract post URLs from DOM", exc_info=True)
        return []


async def _extract_profile_username_map(page: Any) -> Dict[str, str]:
    """Extract a mapping of author display names → LinkedIn usernames from DOM.

    Queries the notifications page DOM for ``<a>`` tags whose ``href``
    contains ``/in/<username>`` or ``/company/<slug>`` and builds a
    case-insensitive lookup dict (first occurrence wins).
    """
    try:
        links_data: List[Dict[str, str]] = await page.evaluate(_PROFILE_LINKS_JS)
    except Exception:
        logger.debug("Failed to extract profile links from DOM", exc_info=True)
        return {}

    name_map: Dict[str, str] = {}
    for item in links_data:
        name_lower = item["name"].lower().strip()
        if name_lower and name_lower not in name_map:
            name_map[name_lower] = item["username"]
    return name_map


def _resolve_username(author: str, profile_map: Dict[str, str]) -> Optional[str]:
    """Look up a LinkedIn username for *author* in *profile_map*.

    Tries an exact (case-insensitive) match first, then falls back to a
    substring containment check in both directions.
    """
    author_lower = author.lower().strip()
    username = profile_map.get(author_lower)
    if username:
        return username
    # Fuzzy: author might be a substring of the link text or vice-versa
    for name, uname in profile_map.items():
        if author_lower in name or name in author_lower:
            return uname
    return None


async def _extract_notifications_from_page(
    page: Any, limit: int = 10
) -> List[Dict[str, Any]]:
    """Extract notification items from the LinkedIn notifications page.

    Each notification in the text follows a repeating pattern:
    - Optional: "Unread notification." marker
    - Content line: "Author posted: text..." / "Author reposted ..." / etc.
    - Time line: "5m", "1h", "2d"

    Profile links (``/in/<username>``) are extracted from the DOM so that each
    notification includes the author's LinkedIn username when available.

    Args:
        page: Patchright page object (already navigated to /notifications/).
        limit: Maximum number of notifications to return.

    Returns:
        A list of notification dicts, each with: author, linkedin_username,
        action, text, time_ago, minutes_ago, is_unread.
    """
    main_text = await page.evaluate(
        "() => { const m = document.querySelector('main'); return m ? m.innerText : ''; }"
    )

    logger.debug(f"Notifications text length: {len(main_text)}")

    if not main_text:
        main_text = await page.evaluate("() => document.body.innerText || ''")

    # Extract author → username map from DOM profile links
    profile_map = await _extract_profile_username_map(page)

    # Extract ordered post URLs from notification cards
    post_urls = await _extract_post_urls(page)

    lines = [line.strip() for line in main_text.split("\n") if line.strip()]

    notifications: List[Dict[str, Any]] = []
    unread_flag = False
    seen_event_authors: set[str] = set()

    i = 0
    while i < len(lines) and len(notifications) < limit:
        line = lines[i]
        line_lower = line.lower()

        # Track unread markers
        if line_lower.startswith("unread notification"):
            unread_flag = True
            i += 1
            continue

        # Skip UI chrome
        if line_lower in _SKIP_LINES or line_lower.startswith("status is "):
            i += 1
            continue

        # Try to parse as a notification
        parsed = _parse_notification_line(line)
        if parsed:
            # For event notifications, deduplicate (LinkedIn shows duplicate lines)
            if parsed["action"] == "hosted this event":
                event_key = parsed["author"]
                if event_key in seen_event_authors:
                    i += 1
                    continue
                seen_event_authors.add(event_key)

                # Try to grab event title from next non-duplicate lines
                event_title_parts = []
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    if next_line == line:
                        j += 1
                        continue
                    if _TIME_AGO_RE.match(next_line):
                        break
                    if re.match(r"^\d+\s+Attendees?", next_line, re.IGNORECASE):
                        j += 1
                        continue
                    # Could be the event title (deduplicate)
                    if next_line not in event_title_parts:
                        event_title_parts.append(next_line)
                    j += 1
                if event_title_parts:
                    parsed["text"] = event_title_parts[0]

            # Look ahead for time_ago on the next non-empty, non-status line
            time_ago = None
            j = i + 1
            while j < len(lines):
                candidate = lines[j].strip()
                if candidate.lower().startswith("status is "):
                    j += 1
                    continue
                if candidate.lower().startswith("unread notification"):
                    break
                if _TIME_AGO_RE.match(candidate):
                    time_ago = candidate
                    break
                # Check if this is another notification (stop looking)
                if _parse_notification_line(candidate) is not None:
                    break
                # Skip attendee lines, duplicate lines
                j += 1

            # Map notification index to post URL from card order
            card_index = len(notifications)
            post_url = post_urls[card_index] if card_index < len(post_urls) else None

            notification: Dict[str, Any] = {
                "author": parsed["author"],
                "linkedin_username": _resolve_username(parsed["author"], profile_map),
                "action": parsed["action"],
                "text": parsed["text"],
                "post_url": post_url,
                "time_ago": time_ago,
                "minutes_ago": _parse_time_ago(time_ago),
                "is_unread": unread_flag,
            }
            notifications.append(notification)

            # Reset unread flag after consuming it
            unread_flag = False

        i += 1

    return notifications


def register_notification_tools(mcp: FastMCP) -> None:
    """Register notification tools with the MCP server.

    Args:
        mcp: The MCP server instance
    """

    @mcp.tool(
        annotations=ToolAnnotations(
            title="Get Notifications",
            readOnlyHint=True,
            destructiveHint=False,
            openWorldHint=False,
        )
    )
    async def get_notifications(ctx: Context, limit: int = 10) -> Dict[str, Any]:
        """
        Get recent notifications from the logged-in user's LinkedIn notifications feed.

        Scrapes linkedin.com/notifications/ for the authenticated user's notification
        stream. Returns the most recent notifications, including posts from connections,
        reposts, event invitations, likes, comments, and other activity.

        Args:
            limit: Maximum number of notifications to return (default 10, max 50).
                   LinkedIn loads ~10-15 notifications per page by default; higher
                   limits may trigger scrolling to load more.

        Returns:
            Dict with:
            - notifications (list[dict]): List of notification objects, each with:
                - author (str): Name of the person or organization
                - linkedin_username (str | null): LinkedIn username or company slug extracted
                  from the profile link (e.g. "raydalio", "nvidia"). null when no link found.
                - action (str): What they did: "posted", "reposted", "commented on your post",
                  "liked your post", "hosted this event", etc.
                - text (str): Preview of the notification content
                - post_url (str | null): Full LinkedIn URL to the related post or activity.
                  Can be passed to get_post_content to retrieve the full post text.
                  null when no post link is found in the notification card.
                - time_ago (str | null): Relative timestamp as shown on LinkedIn ("5m", "1h", "2d")
                - minutes_ago (int | null): Numeric equivalent in minutes (5m->5, 1h->60, 2d->2880)
                - is_unread (bool): Whether the notification was marked as unread
            - count (int): Number of notifications returned
        """
        # Clamp limit
        limit = max(1, min(limit, 50))

        try:
            await ensure_authenticated()

            logger.info(f"Scraping notifications (limit={limit})")

            browser = await get_or_create_browser()
            page = browser.page

            await ctx.report_progress(
                progress=10, total=100, message="Navigating to notifications"
            )

            await page.goto(
                "https://www.linkedin.com/notifications/",
                wait_until="domcontentloaded",
                timeout=30000,
            )

            try:
                await page.wait_for_selector("main", timeout=15000)
            except Exception:
                logger.warning(
                    "Timeout waiting for <main> element on notifications page"
                )

            # Wait for content to render
            await asyncio.sleep(3)

            # Scroll to load more if requesting > 10
            if limit > 10:
                scroll_rounds = min((limit - 10) // 5 + 1, 5)
                for _ in range(scroll_rounds):
                    await page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight)"
                    )
                    await asyncio.sleep(2)

            await ctx.report_progress(
                progress=50, total=100, message="Extracting notifications"
            )

            items = await _extract_notifications_from_page(page, limit=limit)

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return {
                "notifications": items,
                "count": len(items),
            }

        except Exception as e:
            return handle_tool_error(e, "get_notifications")
