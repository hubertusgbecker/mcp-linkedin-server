"""
Input validation for MCP tool parameters.

Provides consistent validation and normalization for LinkedIn identifiers
(usernames, company slugs, job IDs, post URLs) before they reach the scraper.
Raises ValueError with actionable messages the LLM can relay to the user.
"""

import re
from typing import Optional


# LinkedIn username: alphanumeric, hyphens, underscores, 3-100 chars
_USERNAME_RE = re.compile(r"^[a-zA-Z0-9._-]{3,100}$")

# LinkedIn job ID: purely numeric
_JOB_ID_RE = re.compile(r"^\d{5,20}$")

# LinkedIn post URLs
_POST_URL_PATTERNS = [
    re.compile(r"https?://(?:www\.)?linkedin\.com/feed/update/urn:li:activity:\d+"),
    re.compile(r"https?://(?:www\.)?linkedin\.com/posts/[a-zA-Z0-9._-]+_"),
    re.compile(r"https?://(?:www\.)?linkedin\.com/feed/update/urn:li:ugcPost:\d+"),
]

# Full LinkedIn profile URL patterns (to detect when user passes full URL)
_PROFILE_URL_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/in/([a-zA-Z0-9._-]+)/?")
_COMPANY_URL_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/company/([a-zA-Z0-9._-]+)/?"
)
_JOB_URL_RE = re.compile(r"https?://(?:www\.)?linkedin\.com/jobs/view/(\d+)/?")


def validate_linkedin_username(username: str) -> str:
    """Validate and normalize a LinkedIn username/slug.

    Accepts raw slugs or full profile URLs (extracts the slug automatically).

    Args:
        username: The LinkedIn username or profile URL.

    Returns:
        Normalized username slug (stripped, lowercase-safe).

    Raises:
        ValueError: If the username is empty, too short, or contains invalid characters.
    """
    if not username or not username.strip():
        raise ValueError(
            "LinkedIn username cannot be empty. "
            "Pass the slug from linkedin.com/in/<slug>, e.g. 'williamhgates'."
        )

    username = username.strip()

    # Auto-extract slug from full URL
    url_match = _PROFILE_URL_RE.match(username)
    if url_match:
        username = url_match.group(1)

    # Strip trailing slashes
    username = username.rstrip("/")

    if not _USERNAME_RE.match(username):
        raise ValueError(
            f"Invalid LinkedIn username '{username}'. "
            "Usernames contain only letters, numbers, hyphens, underscores, and dots "
            "(3-100 characters). Pass just the slug, not a full URL."
        )

    return username


def validate_company_slug(company_name: str) -> str:
    """Validate and normalize a LinkedIn company slug.

    Accepts raw slugs or full company URLs (extracts the slug automatically).

    Args:
        company_name: The company URL slug or full URL.

    Returns:
        Normalized company slug.

    Raises:
        ValueError: If the slug is empty or contains invalid characters.
    """
    if not company_name or not company_name.strip():
        raise ValueError(
            "Company slug cannot be empty. "
            "Pass the slug from linkedin.com/company/<slug>, e.g. 'microsoft'."
        )

    company_name = company_name.strip()

    # Auto-extract slug from full URL
    url_match = _COMPANY_URL_RE.match(company_name)
    if url_match:
        company_name = url_match.group(1)

    company_name = company_name.rstrip("/")

    if not _USERNAME_RE.match(company_name):
        raise ValueError(
            f"Invalid company slug '{company_name}'. "
            "Slugs contain only letters, numbers, hyphens, underscores, and dots "
            "(3-100 characters). Pass just the slug, not a full URL."
        )

    return company_name


def validate_job_id(job_id: str) -> str:
    """Validate and normalize a LinkedIn job ID.

    Accepts numeric IDs or full job URLs (extracts the ID automatically).

    Args:
        job_id: The numeric job ID or full job URL.

    Returns:
        Normalized numeric job ID string.

    Raises:
        ValueError: If the job ID is not numeric or is out of range.
    """
    if not job_id or not job_id.strip():
        raise ValueError(
            "Job ID cannot be empty. "
            "Pass the numeric ID from linkedin.com/jobs/view/<id>/, e.g. '4252026496'."
        )

    job_id = job_id.strip()

    # Auto-extract ID from full URL
    url_match = _JOB_URL_RE.match(job_id)
    if url_match:
        job_id = url_match.group(1)

    job_id = job_id.rstrip("/")

    if not _JOB_ID_RE.match(job_id):
        raise ValueError(
            f"Invalid job ID '{job_id}'. "
            "Job IDs are numeric (5-20 digits). "
            "Pass just the number from linkedin.com/jobs/view/<id>/."
        )

    return job_id


def validate_post_url(post_url: str) -> str:
    """Validate a LinkedIn post URL.

    Args:
        post_url: Full LinkedIn post URL.

    Returns:
        The validated URL (stripped).

    Raises:
        ValueError: If the URL doesn't match any known LinkedIn post URL pattern.
    """
    if not post_url or not post_url.strip():
        raise ValueError(
            "Post URL cannot be empty. "
            "Pass a full LinkedIn post URL, e.g. "
            "'https://www.linkedin.com/feed/update/urn:li:activity:1234567890/'."
        )

    post_url = post_url.strip()

    if not any(pattern.match(post_url) for pattern in _POST_URL_PATTERNS):
        raise ValueError(
            f"Invalid LinkedIn post URL: '{post_url}'. "
            "Expected formats:\n"
            "  - https://www.linkedin.com/feed/update/urn:li:activity:XXXX/\n"
            "  - https://www.linkedin.com/posts/username_slug-XXXX/"
        )

    return post_url


def validate_limit(limit: int, *, min_val: int = 1, max_val: int = 50) -> int:
    """Validate and clamp a limit parameter.

    Args:
        limit: The requested limit.
        min_val: Minimum allowed value.
        max_val: Maximum allowed value.

    Returns:
        Clamped limit within [min_val, max_val].
    """
    return max(min_val, min(limit, max_val))


def validate_search_keywords(keywords: str) -> str:
    """Validate job search keywords.

    Args:
        keywords: Search query string.

    Returns:
        Stripped keywords.

    Raises:
        ValueError: If keywords are empty.
    """
    if not keywords or not keywords.strip():
        raise ValueError(
            "Search keywords cannot be empty. "
            "Provide terms like 'software engineer' or 'data scientist python'."
        )

    return keywords.strip()


def validate_location(location: Optional[str]) -> Optional[str]:
    """Validate an optional location string.

    Args:
        location: Geographic filter or None.

    Returns:
        Stripped location or None if empty.
    """
    if location is None:
        return None
    location = location.strip()
    return location if location else None
