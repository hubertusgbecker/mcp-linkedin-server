"""Tests for input validation utilities."""

import pytest

from mcp_linkedin_server.utils.validation import (
    validate_company_slug,
    validate_job_id,
    validate_limit,
    validate_linkedin_username,
    validate_location,
    validate_post_url,
    validate_search_keywords,
)


# ── validate_linkedin_username ──────────────────────────────────────────


class TestValidateLinkedinUsername:
    def test_valid_simple_username(self):
        assert validate_linkedin_username("williamhgates") == "williamhgates"

    def test_valid_with_hyphens(self):
        assert validate_linkedin_username("john-doe-123") == "john-doe-123"

    def test_valid_with_dots(self):
        assert validate_linkedin_username("jane.doe") == "jane.doe"

    def test_valid_with_underscores(self):
        assert validate_linkedin_username("user_name") == "user_name"

    def test_strips_whitespace(self):
        assert validate_linkedin_username("  hubertusgbecker  ") == "hubertusgbecker"

    def test_extracts_from_full_url(self):
        assert (
            validate_linkedin_username("https://www.linkedin.com/in/williamhgates/")
            == "williamhgates"
        )

    def test_extracts_from_url_without_trailing_slash(self):
        assert (
            validate_linkedin_username("https://linkedin.com/in/satyanadella")
            == "satyanadella"
        )

    def test_strips_trailing_slash(self):
        assert validate_linkedin_username("williamhgates/") == "williamhgates"

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_linkedin_username("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_linkedin_username("   ")

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="Invalid LinkedIn username"):
            validate_linkedin_username("ab")

    def test_special_characters_raises(self):
        with pytest.raises(ValueError, match="Invalid LinkedIn username"):
            validate_linkedin_username("user@name")

    def test_spaces_in_name_raises(self):
        with pytest.raises(ValueError, match="Invalid LinkedIn username"):
            validate_linkedin_username("john doe")


# ── validate_company_slug ───────────────────────────────────────────────


class TestValidateCompanySlug:
    def test_valid_slug(self):
        assert validate_company_slug("microsoft") == "microsoft"

    def test_valid_with_hyphens(self):
        assert validate_company_slug("robert-bosch-gmbh") == "robert-bosch-gmbh"

    def test_extracts_from_url(self):
        assert (
            validate_company_slug("https://www.linkedin.com/company/docker/")
            == "docker"
        )

    def test_extracts_from_url_no_trailing_slash(self):
        assert (
            validate_company_slug("https://linkedin.com/company/anthropic")
            == "anthropic"
        )

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_company_slug("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_company_slug("   ")

    def test_invalid_characters_raises(self):
        with pytest.raises(ValueError, match="Invalid company slug"):
            validate_company_slug("company name with spaces")

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="Invalid company slug"):
            validate_company_slug("ab")


# ── validate_job_id ─────────────────────────────────────────────────────


class TestValidateJobId:
    def test_valid_numeric_id(self):
        assert validate_job_id("4252026496") == "4252026496"

    def test_valid_short_id(self):
        assert validate_job_id("12345") == "12345"

    def test_strips_whitespace(self):
        assert validate_job_id("  4252026496  ") == "4252026496"

    def test_extracts_from_url(self):
        assert (
            validate_job_id("https://www.linkedin.com/jobs/view/4252026496/")
            == "4252026496"
        )

    def test_extracts_from_url_no_trailing_slash(self):
        assert (
            validate_job_id("https://linkedin.com/jobs/view/4252026496") == "4252026496"
        )

    def test_strips_trailing_slash(self):
        assert validate_job_id("4252026496/") == "4252026496"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_job_id("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_job_id("   ")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="Invalid job ID"):
            validate_job_id("abc123")

    def test_too_short_raises(self):
        with pytest.raises(ValueError, match="Invalid job ID"):
            validate_job_id("1234")

    def test_mixed_raises(self):
        with pytest.raises(ValueError, match="Invalid job ID"):
            validate_job_id("42520abc")


# ── validate_post_url ───────────────────────────────────────────────────


class TestValidatePostUrl:
    def test_valid_activity_url(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:1234567890/"
        assert validate_post_url(url) == url

    def test_valid_activity_url_no_trailing_slash(self):
        url = "https://www.linkedin.com/feed/update/urn:li:activity:1234567890"
        assert validate_post_url(url) == url

    def test_valid_posts_url(self):
        url = "https://www.linkedin.com/posts/johndoe_some-slug-1234/"
        assert validate_post_url(url) == url

    def test_valid_ugc_post_url(self):
        url = "https://www.linkedin.com/feed/update/urn:li:ugcPost:1234567890"
        assert validate_post_url(url) == url

    def test_strips_whitespace(self):
        url = "  https://www.linkedin.com/feed/update/urn:li:activity:1234567890/  "
        assert validate_post_url(url) == url.strip()

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_post_url("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_post_url("   ")

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Invalid LinkedIn post URL"):
            validate_post_url("https://google.com/some-page")

    def test_profile_url_raises(self):
        with pytest.raises(ValueError, match="Invalid LinkedIn post URL"):
            validate_post_url("https://www.linkedin.com/in/williamhgates/")

    def test_plain_text_raises(self):
        with pytest.raises(ValueError, match="Invalid LinkedIn post URL"):
            validate_post_url("not a url at all")


# ── validate_limit ──────────────────────────────────────────────────────


class TestValidateLimit:
    def test_within_range(self):
        assert validate_limit(10) == 10

    def test_clamps_below_min(self):
        assert validate_limit(0) == 1

    def test_clamps_above_max(self):
        assert validate_limit(100) == 50

    def test_negative_clamps_to_min(self):
        assert validate_limit(-5) == 1

    def test_custom_range(self):
        assert validate_limit(200, min_val=5, max_val=100) == 100

    def test_custom_range_below(self):
        assert validate_limit(2, min_val=5, max_val=100) == 5

    def test_exact_min(self):
        assert validate_limit(1) == 1

    def test_exact_max(self):
        assert validate_limit(50) == 50


# ── validate_search_keywords ────────────────────────────────────────────


class TestValidateSearchKeywords:
    def test_valid_keywords(self):
        assert validate_search_keywords("software engineer") == "software engineer"

    def test_strips_whitespace(self):
        assert validate_search_keywords("  python  ") == "python"

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_search_keywords("")

    def test_whitespace_only_raises(self):
        with pytest.raises(ValueError, match="cannot be empty"):
            validate_search_keywords("   ")


# ── validate_location ──────────────────────────────────────────────────


class TestValidateLocation:
    def test_valid_location(self):
        assert validate_location("San Francisco") == "San Francisco"

    def test_strips_whitespace(self):
        assert validate_location("  Berlin  ") == "Berlin"

    def test_none_returns_none(self):
        assert validate_location(None) is None

    def test_empty_returns_none(self):
        assert validate_location("") is None

    def test_whitespace_only_returns_none(self):
        assert validate_location("   ") is None
