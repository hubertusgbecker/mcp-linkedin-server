"""Tests for mcp_linkedin_server.error_handler — all exception types."""

import logging

from linkedin_scraper.core.exceptions import (
    AuthenticationError,
    ElementNotFoundError,
    LinkedInScraperException,
    NetworkError,
    ProfileNotFoundError,
    RateLimitError,
    ScrapingError,
)

from mcp_linkedin_server.error_handler import (
    convert_exception_to_response,
    handle_tool_error,
)
from mcp_linkedin_server.exceptions import (
    CredentialsNotFoundError,
    LinkedInMCPError,
    SessionExpiredError,
)


# ── ValueError / invalid_input ──────────────────────────────────────────


class TestValueError:
    def test_returns_invalid_input(self):
        result = handle_tool_error(ValueError("bad input"), "tool")
        assert result["error"] == "invalid_input"
        assert result["message"] == "bad input"

    def test_no_resolution_key(self):
        result = handle_tool_error(ValueError("x"), "tool")
        assert "resolution" not in result


# ── CredentialsNotFoundError ────────────────────────────────────────────


class TestCredentialsNotFound:
    def test_returns_authentication_not_found(self):
        result = handle_tool_error(CredentialsNotFoundError("no creds"), "tool")
        assert result["error"] == "authentication_not_found"
        assert "no creds" in result["message"]
        assert "resolution" in result


# ── SessionExpiredError ─────────────────────────────────────────────────


class TestSessionExpired:
    def test_returns_session_expired(self):
        result = handle_tool_error(SessionExpiredError(), "test_tool")
        assert result["error"] == "session_expired"
        assert "message" in result
        assert "resolution" in result

    def test_custom_message(self):
        result = handle_tool_error(SessionExpiredError("custom msg"), "tool")
        assert "custom msg" in result["message"]


# ── AuthenticationError ─────────────────────────────────────────────────


class TestAuthenticationError:
    def test_returns_authentication_failed(self):
        result = handle_tool_error(AuthenticationError("auth fail"), "tool")
        assert result["error"] == "authentication_failed"
        assert "resolution" in result


# ── RateLimitError ──────────────────────────────────────────────────────


class TestRateLimitError:
    def test_with_custom_wait_time(self):
        err = RateLimitError("blocked")
        err.suggested_wait_time = 600  # type: ignore[attr-defined]
        result = handle_tool_error(err, "tool")
        assert result["error"] == "rate_limit"
        assert result["suggested_wait_seconds"] == 600
        assert "600" in result["resolution"]

    def test_default_wait_time(self):
        result = handle_tool_error(RateLimitError("blocked"), "tool")
        assert result["suggested_wait_seconds"] == 300
        assert "300" in result["resolution"]


# ── ProfileNotFoundError ───────────────────────────────────────────────


class TestProfileNotFoundError:
    def test_returns_profile_not_found(self):
        result = handle_tool_error(ProfileNotFoundError("no profile"), "tool")
        assert result["error"] == "profile_not_found"
        assert "resolution" in result


# ── ElementNotFoundError ───────────────────────────────────────────────


class TestElementNotFoundError:
    def test_returns_element_not_found(self):
        result = handle_tool_error(ElementNotFoundError("missing element"), "tool")
        assert result["error"] == "element_not_found"
        assert "page structure" in result["resolution"].lower()


# ── NetworkError ───────────────────────────────────────────────────────


class TestNetworkError:
    def test_returns_network_error(self):
        result = handle_tool_error(NetworkError("timeout"), "tool")
        assert result["error"] == "network_error"
        assert "resolution" in result


# ── ScrapingError ──────────────────────────────────────────────────────


class TestScrapingError:
    def test_returns_scraping_error(self):
        result = handle_tool_error(ScrapingError("parse fail"), "tool")
        assert result["error"] == "scraping_error"
        assert "resolution" in result


# ── LinkedInScraperException ───────────────────────────────────────────


class TestLinkedInScraperException:
    def test_returns_scraper_error(self):
        result = handle_tool_error(LinkedInScraperException("generic"), "tool")
        assert result["error"] == "mcp_linkedin_server_error"
        assert "generic" in result["message"]

    def test_no_resolution_key(self):
        result = handle_tool_error(LinkedInScraperException("x"), "tool")
        assert "resolution" not in result


# ── LinkedInMCPError ───────────────────────────────────────────────────


class TestLinkedInMCPError:
    def test_returns_linkedin_mcp_error(self):
        result = handle_tool_error(LinkedInMCPError("mcp err"), "tool")
        assert result["error"] == "linkedin_mcp_error"
        assert "mcp err" in result["message"]


# ── Unknown / generic Exception ────────────────────────────────────────


class TestGenericException:
    def test_returns_unknown_error(self):
        result = handle_tool_error(RuntimeError("boom"), "tool_x")
        assert result["error"] == "unknown_error"
        assert "boom" in result["message"]
        assert "tool_x" in result["message"]

    def test_logs_error(self, caplog):
        with caplog.at_level(logging.ERROR, logger="mcp_linkedin_server.error_handler"):
            handle_tool_error(RuntimeError("surprise"), "ctx")
        assert "surprise" in caplog.text


# ── handle_tool_error delegates to convert_exception_to_response ───────


class TestDelegation:
    def test_handle_tool_error_delegates(self):
        """handle_tool_error and convert_exception_to_response produce same result."""
        err = ValueError("same")
        assert handle_tool_error(err, "ctx") == convert_exception_to_response(
            err, "ctx"
        )


# ── Context parameter ─────────────────────────────────────────────────


class TestContext:
    def test_empty_context_defaults_gracefully(self):
        result = handle_tool_error(RuntimeError("err"))
        assert result["error"] == "unknown_error"

    def test_context_appears_in_unknown_error(self):
        result = handle_tool_error(RuntimeError("err"), "get_person_profile")
        assert "get_person_profile" in result["message"]
