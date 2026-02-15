"""Tests for mcp_linkedin_server.drivers.browser — singleton lifecycle and helpers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_linkedin_server.config.schema import AppConfig
from mcp_linkedin_server.drivers.browser import (
    close_browser,
    get_or_create_browser,
    get_profile_dir,
    profile_exists,
    reset_browser_for_testing,
    set_headless,
)


@pytest.fixture(autouse=True)
def _reset_browser():
    """Ensure clean singleton state for each test."""
    reset_browser_for_testing()
    yield
    reset_browser_for_testing()


@pytest.fixture(autouse=True)
def _mock_config(monkeypatch, tmp_path):
    """Provide a test config so get_config() never triggers argparse."""
    config = AppConfig()
    config.browser.user_data_dir = str(tmp_path / "profile")
    monkeypatch.setattr(
        "mcp_linkedin_server.drivers.browser.get_config", lambda: config
    )


def _make_mock_browser(*, logged_in: bool = True) -> MagicMock:
    """Create a mock BrowserManager with controllable login state."""
    browser = MagicMock()
    browser.start = AsyncMock()
    browser.close = AsyncMock()
    browser.page = MagicMock()
    browser.page.goto = AsyncMock()
    browser.page.set_default_timeout = MagicMock()
    browser.import_cookies = AsyncMock(return_value=False)
    browser.export_cookies = AsyncMock(return_value=False)
    return browser


# ── get_or_create_browser ──────────────────────────────────────────────


class TestGetOrCreateBrowser:
    @pytest.mark.asyncio
    async def test_auth_success(self):
        """Successful auth assigns singleton and returns browser."""
        mock_browser = _make_mock_browser()
        with (
            patch(
                "mcp_linkedin_server.drivers.browser.BrowserManager",
                return_value=mock_browser,
            ),
            patch(
                "mcp_linkedin_server.drivers.browser.is_logged_in",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = await get_or_create_browser()
        assert result is mock_browser
        mock_browser.start.assert_awaited_once()
        mock_browser.page.goto.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_auth_failure_cleans_up(self):
        """Failed auth closes browser and does NOT assign singleton."""
        from linkedin_scraper import AuthenticationError

        mock_browser = _make_mock_browser()
        with (
            patch(
                "mcp_linkedin_server.drivers.browser.BrowserManager",
                return_value=mock_browser,
            ),
            patch(
                "mcp_linkedin_server.drivers.browser.is_logged_in",
                new_callable=AsyncMock,
                return_value=False,
            ),
            pytest.raises(AuthenticationError),
        ):
            await get_or_create_browser()
        mock_browser.close.assert_awaited_once()
        from mcp_linkedin_server.drivers.browser import _browser

        assert _browser is None

    @pytest.mark.asyncio
    async def test_singleton_returns_existing(self):
        """Second call returns the same browser instance (singleton)."""
        mock_browser = _make_mock_browser()
        with (
            patch(
                "mcp_linkedin_server.drivers.browser.BrowserManager",
                return_value=mock_browser,
            ) as ctor,
            patch(
                "mcp_linkedin_server.drivers.browser.is_logged_in",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            first = await get_or_create_browser()
            second = await get_or_create_browser()
        assert first is second
        ctor.assert_called_once()


# ── close_browser ──────────────────────────────────────────────────────


class TestCloseBrowser:
    @pytest.mark.asyncio
    async def test_close_when_no_browser(self):
        """close_browser with no active browser should not raise."""
        await close_browser()  # No error

    @pytest.mark.asyncio
    async def test_close_sets_singleton_to_none(self):
        """After close, the singleton should be reset."""
        import mcp_linkedin_server.drivers.browser as mod

        mock_browser = MagicMock()
        mock_browser.close = AsyncMock()
        mock_browser.export_cookies = AsyncMock(return_value=True)
        mod._browser = mock_browser

        await close_browser()
        assert mod._browser is None
        mock_browser.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_exports_cookies_before_closing(self):
        """Cookies should be exported before browser is closed."""
        import mcp_linkedin_server.drivers.browser as mod

        call_order = []
        mock_browser = MagicMock()
        mock_browser.export_cookies = AsyncMock(
            side_effect=lambda: call_order.append("export")
        )
        mock_browser.close = AsyncMock(side_effect=lambda: call_order.append("close"))
        mod._browser = mock_browser

        await close_browser()
        assert call_order == ["export", "close"]

    @pytest.mark.asyncio
    async def test_close_survives_export_failure(self):
        """If cookie export fails, browser should still close."""
        import mcp_linkedin_server.drivers.browser as mod

        mock_browser = MagicMock()
        mock_browser.export_cookies = AsyncMock(side_effect=RuntimeError("fail"))
        mock_browser.close = AsyncMock()
        mod._browser = mock_browser

        await close_browser()
        assert mod._browser is None
        mock_browser.close.assert_awaited_once()


# ── set_headless ───────────────────────────────────────────────────────


class TestSetHeadless:
    def test_set_true(self):
        import mcp_linkedin_server.drivers.browser as mod

        set_headless(True)
        assert mod._headless is True

    def test_set_false(self):
        import mcp_linkedin_server.drivers.browser as mod

        set_headless(False)
        assert mod._headless is False


# ── reset_browser_for_testing ──────────────────────────────────────────


class TestResetBrowser:
    def test_resets_browser_and_headless(self):
        import mcp_linkedin_server.drivers.browser as mod

        mod._browser = MagicMock()
        mod._headless = False
        reset_browser_for_testing()
        assert mod._browser is None
        assert mod._headless is True


# ── profile_exists ─────────────────────────────────────────────────────


class TestProfileExists:
    def test_nonexistent_dir(self, tmp_path):
        assert profile_exists(tmp_path / "nope") is False

    def test_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert profile_exists(d) is False

    def test_non_empty_dir(self, tmp_path):
        d = tmp_path / "profile"
        d.mkdir()
        (d / "file.txt").write_text("x")
        assert profile_exists(d) is True

    def test_file_not_dir(self, tmp_path):
        f = tmp_path / "file"
        f.write_text("data")
        assert profile_exists(f) is False

    def test_default_uses_config(self, monkeypatch, tmp_path):
        """profile_exists() with no arg uses get_profile_dir()."""
        d = tmp_path / "default_profile"
        d.mkdir()
        (d / "marker").write_text("x")
        monkeypatch.setattr(
            "mcp_linkedin_server.drivers.browser.get_profile_dir", lambda: d
        )
        assert profile_exists() is True


# ── get_profile_dir ────────────────────────────────────────────────────


class TestGetProfileDir:
    def test_returns_path(self, tmp_path, monkeypatch):
        config = AppConfig()
        config.browser.user_data_dir = str(tmp_path / "custom")
        monkeypatch.setattr(
            "mcp_linkedin_server.drivers.browser.get_config", lambda: config
        )
        result = get_profile_dir()
        assert result == tmp_path / "custom"

    def test_expands_tilde(self, monkeypatch):
        config = AppConfig()
        config.browser.user_data_dir = "~/test_profile"
        monkeypatch.setattr(
            "mcp_linkedin_server.drivers.browser.get_config", lambda: config
        )
        result = get_profile_dir()
        assert "~" not in str(result)
        assert str(result).endswith("test_profile")


# ── validate_session ───────────────────────────────────────────────────


class TestValidateSession:
    @pytest.mark.asyncio
    async def test_valid_session(self):
        mock_browser = _make_mock_browser()
        with (
            patch(
                "mcp_linkedin_server.drivers.browser.BrowserManager",
                return_value=mock_browser,
            ),
            patch(
                "mcp_linkedin_server.drivers.browser.is_logged_in",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            from mcp_linkedin_server.drivers.browser import validate_session

            result = await validate_session()
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_session(self):
        from linkedin_scraper import AuthenticationError

        mock_browser = _make_mock_browser()
        with (
            patch(
                "mcp_linkedin_server.drivers.browser.BrowserManager",
                return_value=mock_browser,
            ),
            patch(
                "mcp_linkedin_server.drivers.browser.is_logged_in",
                new_callable=AsyncMock,
                return_value=False,
            ),
            pytest.raises(AuthenticationError),
        ):
            from mcp_linkedin_server.drivers.browser import validate_session

            await validate_session()


# ── ensure_authenticated ───────────────────────────────────────────────


class TestEnsureAuthenticated:
    @pytest.mark.asyncio
    async def test_raises_when_not_logged_in(self):
        from linkedin_scraper import AuthenticationError

        mock_browser = _make_mock_browser()
        with (
            patch(
                "mcp_linkedin_server.drivers.browser.BrowserManager",
                return_value=mock_browser,
            ),
            patch(
                "mcp_linkedin_server.drivers.browser.is_logged_in",
                new_callable=AsyncMock,
                return_value=False,
            ),
            pytest.raises(AuthenticationError),
        ):
            from mcp_linkedin_server.drivers.browser import ensure_authenticated

            await ensure_authenticated()


# ── check_rate_limit ───────────────────────────────────────────────────


class TestCheckRateLimit:
    @pytest.mark.asyncio
    async def test_delegates_to_detect_rate_limit(self):
        mock_browser = _make_mock_browser()
        with (
            patch(
                "mcp_linkedin_server.drivers.browser.BrowserManager",
                return_value=mock_browser,
            ),
            patch(
                "mcp_linkedin_server.drivers.browser.is_logged_in",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "mcp_linkedin_server.drivers.browser.detect_rate_limit",
                new_callable=AsyncMock,
            ) as mock_detect,
        ):
            from mcp_linkedin_server.drivers.browser import check_rate_limit

            await check_rate_limit()
            mock_detect.assert_awaited_once()
