"""Tests for cli_main.py: testable units and branches."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp_linkedin_server.config.schema import AppConfig


# ── get_version ────────────────────────────────────────────────────────


class TestGetVersion:
    def test_returns_version_string(self):
        from mcp_linkedin_server.cli_main import get_version

        version = get_version()
        # Should be a dotted version or "unknown"
        assert isinstance(version, str)
        assert version != ""

    def test_returns_unknown_on_error(self, monkeypatch):
        """If pyproject.toml cannot be read, returns 'unknown'."""
        from mcp_linkedin_server import cli_main

        original_open = open

        def broken_open(*args, **kwargs):
            if "pyproject.toml" in str(args[0]):
                raise FileNotFoundError("nope")
            return original_open(*args, **kwargs)

        monkeypatch.setattr("builtins.open", broken_open)
        assert cli_main.get_version() == "unknown"


# ── ensure_authentication_ready ────────────────────────────────────────


class TestEnsureAuthReady:
    def test_returns_when_profile_exists(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog"])
        from mcp_linkedin_server.cli_main import ensure_authentication_ready

        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.get_authentication_source",
            lambda: True,
        )
        ensure_authentication_ready()  # No error

    def test_raises_when_non_interactive(self, monkeypatch):
        from mcp_linkedin_server.cli_main import ensure_authentication_ready
        from mcp_linkedin_server.exceptions import CredentialsNotFoundError

        def raise_creds():
            raise CredentialsNotFoundError("no creds")

        config = AppConfig()
        config.is_interactive = False
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.get_authentication_source", raise_creds
        )
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        with pytest.raises(CredentialsNotFoundError):
            ensure_authentication_ready()

    def test_runs_interactive_setup_when_interactive(self, monkeypatch):
        from mcp_linkedin_server.cli_main import ensure_authentication_ready
        from mcp_linkedin_server.exceptions import CredentialsNotFoundError

        def raise_creds():
            raise CredentialsNotFoundError("no creds")

        config = AppConfig()
        config.is_interactive = True
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.get_authentication_source", raise_creds
        )
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.run_interactive_setup", lambda: True
        )
        ensure_authentication_ready()  # No error — interactive setup succeeded

    def test_raises_when_interactive_setup_fails(self, monkeypatch):
        from mcp_linkedin_server.cli_main import ensure_authentication_ready
        from mcp_linkedin_server.exceptions import CredentialsNotFoundError

        def raise_creds():
            raise CredentialsNotFoundError("no creds")

        config = AppConfig()
        config.is_interactive = True
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.get_authentication_source", raise_creds
        )
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.run_interactive_setup", lambda: False
        )
        with pytest.raises(CredentialsNotFoundError, match="cancelled or failed"):
            ensure_authentication_ready()


# ── choose_transport_interactive ───────────────────────────────────────


class TestChooseTransport:
    def test_returns_selected_transport(self, monkeypatch):
        from mcp_linkedin_server.cli_main import choose_transport_interactive

        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.inquirer.prompt",
            lambda _: {"transport": "streamable-http"},
        )
        assert choose_transport_interactive() == "streamable-http"

    def test_raises_on_cancel(self, monkeypatch):
        from mcp_linkedin_server.cli_main import choose_transport_interactive

        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.inquirer.prompt", lambda _: None
        )
        with pytest.raises(KeyboardInterrupt):
            choose_transport_interactive()


# ── exit_gracefully ────────────────────────────────────────────────────


class TestExitGracefully:
    def test_calls_close_browser(self, monkeypatch):
        from mcp_linkedin_server.cli_main import exit_gracefully

        closed = []
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.close_browser",
            AsyncMock(side_effect=lambda: closed.append(True)),
        )
        with pytest.raises(SystemExit) as exc_info:
            exit_gracefully(0)
        assert exc_info.value.code == 0
        assert closed

    def test_survives_close_error(self, monkeypatch):
        from mcp_linkedin_server.cli_main import exit_gracefully

        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.close_browser",
            AsyncMock(side_effect=RuntimeError("boom")),
        )
        with pytest.raises(SystemExit) as exc_info:
            exit_gracefully(1)
        assert exc_info.value.code == 1


# ── clear_profile_and_exit ─────────────────────────────────────────────


class TestClearProfileAndExit:
    def test_no_profile_exits_0(self, monkeypatch):
        from mcp_linkedin_server.cli_main import clear_profile_and_exit

        config = AppConfig()
        monkeypatch.setattr("sys.argv", ["prog"])
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.profile_exists", lambda _: False
        )
        with pytest.raises(SystemExit) as exc_info:
            clear_profile_and_exit()
        assert exc_info.value.code == 0

    def test_cancel_exits_0(self, monkeypatch):
        from mcp_linkedin_server.cli_main import clear_profile_and_exit

        config = AppConfig()
        monkeypatch.setattr("sys.argv", ["prog"])
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.profile_exists", lambda _: True
        )
        monkeypatch.setattr("builtins.input", lambda _: "n")
        with pytest.raises(SystemExit) as exc_info:
            clear_profile_and_exit()
        assert exc_info.value.code == 0

    def test_confirm_clears_and_exits_0(self, monkeypatch, tmp_path):
        from mcp_linkedin_server.cli_main import clear_profile_and_exit

        config = AppConfig()
        monkeypatch.setattr("sys.argv", ["prog"])
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.profile_exists", lambda _: True
        )
        monkeypatch.setattr("builtins.input", lambda _: "y")
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.clear_profile", lambda _: True
        )
        with pytest.raises(SystemExit) as exc_info:
            clear_profile_and_exit()
        assert exc_info.value.code == 0

    def test_clear_failure_exits_1(self, monkeypatch):
        from mcp_linkedin_server.cli_main import clear_profile_and_exit

        config = AppConfig()
        monkeypatch.setattr("sys.argv", ["prog"])
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.profile_exists", lambda _: True
        )
        monkeypatch.setattr("builtins.input", lambda _: "yes")
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.clear_profile", lambda _: False
        )
        with pytest.raises(SystemExit) as exc_info:
            clear_profile_and_exit()
        assert exc_info.value.code == 1

    def test_keyboard_interrupt(self, monkeypatch):
        from mcp_linkedin_server.cli_main import clear_profile_and_exit

        config = AppConfig()
        monkeypatch.setattr("sys.argv", ["prog"])
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.profile_exists", lambda _: True
        )

        def raise_keyboard(_):
            raise KeyboardInterrupt

        monkeypatch.setattr("builtins.input", raise_keyboard)
        with pytest.raises(SystemExit) as exc_info:
            clear_profile_and_exit()
        assert exc_info.value.code == 0


# ── get_profile_and_exit ───────────────────────────────────────────────


class TestGetProfileAndExit:
    def test_success_exits_0(self, monkeypatch):
        from mcp_linkedin_server.cli_main import get_profile_and_exit

        config = AppConfig()
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.run_profile_creation", lambda _: True
        )
        with pytest.raises(SystemExit) as exc_info:
            get_profile_and_exit()
        assert exc_info.value.code == 0

    def test_failure_exits_1(self, monkeypatch):
        from mcp_linkedin_server.cli_main import get_profile_and_exit

        config = AppConfig()
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.run_profile_creation", lambda _: False
        )
        with pytest.raises(SystemExit) as exc_info:
            get_profile_and_exit()
        assert exc_info.value.code == 1


# ── profile_info_and_exit ──────────────────────────────────────────────


class TestProfileInfoAndExit:
    def test_no_profile_exits_1(self, monkeypatch):
        from mcp_linkedin_server.cli_main import profile_info_and_exit

        config = AppConfig()
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.profile_exists", lambda _: False
        )
        with pytest.raises(SystemExit) as exc_info:
            profile_info_and_exit()
        assert exc_info.value.code == 1

    def test_valid_session_exits_0(self, monkeypatch):
        from mcp_linkedin_server.cli_main import profile_info_and_exit

        config = AppConfig()
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.profile_exists", lambda _: True
        )
        monkeypatch.setattr("mcp_linkedin_server.cli_main.set_headless", lambda _: None)
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.is_logged_in",
            AsyncMock(return_value=True),
        )
        monkeypatch.setattr("mcp_linkedin_server.cli_main.close_browser", AsyncMock())
        with pytest.raises(SystemExit) as exc_info:
            profile_info_and_exit()
        assert exc_info.value.code == 0

    def test_expired_session_exits_1(self, monkeypatch):
        from mcp_linkedin_server.cli_main import profile_info_and_exit

        config = AppConfig()
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.profile_exists", lambda _: True
        )
        monkeypatch.setattr("mcp_linkedin_server.cli_main.set_headless", lambda _: None)
        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.is_logged_in",
            AsyncMock(return_value=False),
        )
        monkeypatch.setattr("mcp_linkedin_server.cli_main.close_browser", AsyncMock())
        with pytest.raises(SystemExit) as exc_info:
            profile_info_and_exit()
        assert exc_info.value.code == 1

    def test_exception_during_check_exits_1(self, monkeypatch):
        from mcp_linkedin_server.cli_main import profile_info_and_exit

        config = AppConfig()
        monkeypatch.setattr("mcp_linkedin_server.cli_main.get_config", lambda: config)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.profile_exists", lambda _: True
        )
        monkeypatch.setattr("mcp_linkedin_server.cli_main.set_headless", lambda _: None)
        monkeypatch.setattr(
            "mcp_linkedin_server.cli_main.get_or_create_browser",
            AsyncMock(side_effect=RuntimeError("browser crashed")),
        )
        monkeypatch.setattr("mcp_linkedin_server.cli_main.close_browser", AsyncMock())
        with pytest.raises(SystemExit) as exc_info:
            profile_info_and_exit()
        assert exc_info.value.code == 1
