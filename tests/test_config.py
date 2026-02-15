"""Tests for config schema, loaders, and singleton."""

import argparse
import io

import pytest

from mcp_linkedin_server.config.schema import (
    AppConfig,
    BrowserConfig,
    ConfigurationError,
    ServerConfig,
)


# ── BrowserConfig ──────────────────────────────────────────────────────


class TestBrowserConfig:
    def test_defaults(self):
        config = BrowserConfig()
        assert config.headless is True
        assert config.default_timeout == 5000
        assert config.user_data_dir == "~/.linkedin-mcp/profile"

    def test_validate_passes(self):
        BrowserConfig().validate()  # No error

    def test_validate_negative_timeout(self):
        with pytest.raises(ConfigurationError):
            BrowserConfig(default_timeout=-1).validate()

    def test_validate_negative_slow_mo(self):
        with pytest.raises(ConfigurationError):
            BrowserConfig(slow_mo=-1).validate()

    def test_zero_viewport_width_raises(self):
        with pytest.raises(ConfigurationError, match="viewport dimensions"):
            BrowserConfig(viewport_width=0).validate()

    def test_negative_viewport_height_raises(self):
        with pytest.raises(ConfigurationError, match="viewport dimensions"):
            BrowserConfig(viewport_height=-1).validate()

    def test_chrome_path_not_exists_raises(self, tmp_path):
        fake = str(tmp_path / "nonexistent")
        with pytest.raises(ConfigurationError, match="does not exist"):
            BrowserConfig(chrome_path=fake).validate()

    def test_chrome_path_is_directory_raises(self, tmp_path):
        d = tmp_path / "dir"
        d.mkdir()
        with pytest.raises(ConfigurationError, match="is not a file"):
            BrowserConfig(chrome_path=str(d)).validate()

    def test_chrome_path_valid_file(self, tmp_path):
        f = tmp_path / "chrome"
        f.write_text("binary")
        BrowserConfig(chrome_path=str(f)).validate()  # No error

    def test_zero_slow_mo_is_valid(self):
        BrowserConfig(slow_mo=0).validate()  # No error

    def test_large_timeout_is_valid(self):
        BrowserConfig(default_timeout=60000).validate()  # No error


# ── ServerConfig ───────────────────────────────────────────────────────


class TestServerConfig:
    def test_all_defaults(self):
        cfg = ServerConfig()
        assert cfg.transport == "stdio"
        assert cfg.transport_explicitly_set is False
        assert cfg.log_level == "WARNING"
        assert cfg.get_session is False
        assert cfg.session_info is False
        assert cfg.clear_session is False
        assert cfg.host == "127.0.0.1"
        assert cfg.port == 8000
        assert cfg.path == "/mcp"


# ── AppConfig: transport validation ────────────────────────────────────


class TestTransportValidation:
    def test_streamable_http_valid(self):
        cfg = AppConfig()
        cfg.server.transport = "streamable-http"
        cfg.validate()  # No error

    def test_sse_valid(self):
        cfg = AppConfig()
        cfg.server.transport = "sse"
        cfg.validate()  # No error

    def test_http_transport_empty_host_raises(self):
        cfg = AppConfig()
        cfg.server.transport = "streamable-http"
        cfg.server.host = ""
        with pytest.raises(ConfigurationError, match="valid host"):
            cfg.validate()

    def test_http_transport_zero_port_raises(self):
        cfg = AppConfig()
        cfg.server.transport = "streamable-http"
        cfg.server.port = 0
        with pytest.raises(ConfigurationError, match="valid port|valid range"):
            cfg.validate()


# ── AppConfig: path validation ─────────────────────────────────────────


class TestPathValidation:
    def test_path_without_leading_slash_raises(self):
        cfg = AppConfig()
        cfg.server.transport = "streamable-http"
        cfg.server.path = "mcp"
        with pytest.raises(ConfigurationError, match="must start with"):
            cfg.validate()

    def test_single_slash_path_raises(self):
        cfg = AppConfig()
        cfg.server.transport = "streamable-http"
        cfg.server.path = "/"
        with pytest.raises(ConfigurationError, match="at least 2 characters"):
            cfg.validate()

    def test_valid_nested_path(self):
        cfg = AppConfig()
        cfg.server.transport = "streamable-http"
        cfg.server.path = "/api/mcp"
        cfg.validate()  # No error

    def test_stdio_skips_path_validation(self):
        cfg = AppConfig()
        cfg.server.transport = "stdio"
        cfg.server.path = "no-slash"  # Would fail for HTTP
        cfg.validate()  # No error for stdio


# ── AppConfig: port range ──────────────────────────────────────────────


class TestPortRange:
    def test_port_zero_raises(self):
        cfg = AppConfig()
        cfg.server.port = 0
        with pytest.raises(ConfigurationError, match="valid range"):
            cfg.validate()

    def test_port_65536_raises(self):
        cfg = AppConfig()
        cfg.server.port = 65536
        with pytest.raises(ConfigurationError, match="valid range"):
            cfg.validate()

    def test_port_1_valid(self):
        cfg = AppConfig()
        cfg.server.port = 1
        cfg.validate()

    def test_port_65535_valid(self):
        cfg = AppConfig()
        cfg.server.port = 65535
        cfg.validate()

    def test_negative_port_raises(self):
        cfg = AppConfig()
        cfg.server.port = -1
        with pytest.raises(ConfigurationError):
            cfg.validate()


# ── Config singleton ───────────────────────────────────────────────────


class TestConfigSingleton:
    def test_get_config_returns_same_instance(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["linkedin-mcp-server"])
        from mcp_linkedin_server.config import get_config

        assert get_config() is get_config()

    def test_reset_config_clears_singleton(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["linkedin-mcp-server"])
        from mcp_linkedin_server.config import get_config, reset_config

        first = get_config()
        reset_config()
        second = get_config()
        assert first is not second


# ── load_from_env ──────────────────────────────────────────────────────


class TestLoadFromEnv:
    def test_headless_false(self, monkeypatch):
        monkeypatch.setenv("HEADLESS", "false")
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.browser.headless is False

    def test_headless_true(self, monkeypatch):
        monkeypatch.setenv("HEADLESS", "true")
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.browser.headless is True

    def test_log_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.server.log_level == "DEBUG"

    def test_defaults_without_env(self, monkeypatch):
        for var in ["HEADLESS", "LOG_LEVEL"]:
            monkeypatch.delenv(var, raising=False)
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.browser.headless is True

    def test_transport_streamable_http(self, monkeypatch):
        monkeypatch.setenv("TRANSPORT", "streamable-http")
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.server.transport == "streamable-http"
        assert config.server.transport_explicitly_set is True

    def test_transport_sse(self, monkeypatch):
        monkeypatch.setenv("TRANSPORT", "sse")
        from mcp_linkedin_server.config.loaders import load_from_env

        cfg = load_from_env(AppConfig())
        assert cfg.server.transport == "sse"
        assert cfg.server.transport_explicitly_set is True

    def test_invalid_transport(self, monkeypatch):
        monkeypatch.setenv("TRANSPORT", "invalid")
        from mcp_linkedin_server.config.loaders import load_from_env

        with pytest.raises(ConfigurationError, match="Invalid TRANSPORT"):
            load_from_env(AppConfig())

    def test_timeout(self, monkeypatch):
        monkeypatch.setenv("TIMEOUT", "10000")
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.browser.default_timeout == 10000

    def test_invalid_timeout(self, monkeypatch):
        monkeypatch.setenv("TIMEOUT", "invalid")
        from mcp_linkedin_server.config.loaders import load_from_env

        with pytest.raises(ConfigurationError, match="Invalid TIMEOUT"):
            load_from_env(AppConfig())

    def test_port(self, monkeypatch):
        monkeypatch.setenv("PORT", "9000")
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.server.port == 9000

    def test_invalid_port(self, monkeypatch):
        monkeypatch.setenv("PORT", "not_a_number")
        from mcp_linkedin_server.config.loaders import load_from_env

        with pytest.raises(ConfigurationError, match="Invalid PORT"):
            load_from_env(AppConfig())

    def test_slow_mo(self, monkeypatch):
        monkeypatch.setenv("SLOW_MO", "100")
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.browser.slow_mo == 100

    def test_invalid_slow_mo(self, monkeypatch):
        monkeypatch.setenv("SLOW_MO", "abc")
        from mcp_linkedin_server.config.loaders import load_from_env

        with pytest.raises(ConfigurationError, match="Invalid SLOW_MO"):
            load_from_env(AppConfig())

    def test_viewport(self, monkeypatch):
        monkeypatch.setenv("VIEWPORT", "1920x1080")
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.browser.viewport_width == 1920
        assert config.browser.viewport_height == 1080

    def test_invalid_viewport(self, monkeypatch):
        monkeypatch.setenv("VIEWPORT", "invalid")
        from mcp_linkedin_server.config.loaders import load_from_env

        with pytest.raises(ConfigurationError, match="Invalid VIEWPORT"):
            load_from_env(AppConfig())

    def test_user_data_dir(self, monkeypatch):
        monkeypatch.setenv("USER_DATA_DIR", "/custom/profile")
        from mcp_linkedin_server.config.loaders import load_from_env

        config = load_from_env(AppConfig())
        assert config.browser.user_data_dir == "/custom/profile"

    def test_host(self, monkeypatch):
        monkeypatch.setenv("HOST", "0.0.0.0")
        from mcp_linkedin_server.config.loaders import load_from_env

        cfg = load_from_env(AppConfig())
        assert cfg.server.host == "0.0.0.0"

    def test_http_path(self, monkeypatch):
        monkeypatch.setenv("HTTP_PATH", "/api/v2")
        from mcp_linkedin_server.config.loaders import load_from_env

        cfg = load_from_env(AppConfig())
        assert cfg.server.path == "/api/v2"

    def test_chrome_path(self, monkeypatch):
        monkeypatch.setenv("CHROME_PATH", "/usr/bin/chromium")
        from mcp_linkedin_server.config.loaders import load_from_env

        cfg = load_from_env(AppConfig())
        assert cfg.browser.chrome_path == "/usr/bin/chromium"

    def test_user_agent(self, monkeypatch):
        monkeypatch.setenv("USER_AGENT", "CustomBot/1.0")
        from mcp_linkedin_server.config.loaders import load_from_env

        cfg = load_from_env(AppConfig())
        assert cfg.browser.user_agent == "CustomBot/1.0"


# ── load_from_args ─────────────────────────────────────────────────────


class TestLoadFromArgs:
    def test_no_headless_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--no-headless"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.browser.headless is False

    def test_log_level_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--log-level", "DEBUG"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.server.log_level == "DEBUG"

    def test_transport_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--transport", "streamable-http"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.server.transport == "streamable-http"
        assert cfg.server.transport_explicitly_set is True

    def test_host_and_port_flags(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--host", "0.0.0.0", "--port", "9000"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.server.host == "0.0.0.0"
        assert cfg.server.port == 9000

    def test_path_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--path", "/v2"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.server.path == "/v2"

    def test_viewport_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--viewport", "1920x1080"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.browser.viewport_width == 1920
        assert cfg.browser.viewport_height == 1080

    def test_invalid_viewport_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--viewport", "bad"])
        from mcp_linkedin_server.config.loaders import load_from_args

        with pytest.raises(ConfigurationError, match="Invalid --viewport"):
            load_from_args(AppConfig())

    def test_timeout_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--timeout", "10000"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.browser.default_timeout == 10000

    def test_chrome_path_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--chrome-path", "/usr/bin/chrome"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.browser.chrome_path == "/usr/bin/chrome"

    def test_get_session_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--get-session"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.server.get_session is True

    def test_session_info_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--session-info"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.server.session_info is True

    def test_clear_session_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--clear-session"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.server.clear_session is True

    def test_user_data_dir_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--user-data-dir", "/tmp/profile"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.browser.user_data_dir == "/tmp/profile"

    def test_slow_mo_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--slow-mo", "100"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.browser.slow_mo == 100

    def test_user_agent_flag(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog", "--user-agent", "MyBot"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.browser.user_agent == "MyBot"

    def test_default_args(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["prog"])
        from mcp_linkedin_server.config.loaders import load_from_args

        cfg = load_from_args(AppConfig())
        assert cfg.browser.headless is True
        assert cfg.server.transport == "stdio"


# ── positive_int ───────────────────────────────────────────────────────


class TestPositiveInt:
    def test_valid_positive(self):
        from mcp_linkedin_server.config.loaders import positive_int

        assert positive_int("42") == 42

    def test_zero_raises(self):
        from mcp_linkedin_server.config.loaders import positive_int

        with pytest.raises(argparse.ArgumentTypeError, match="positive"):
            positive_int("0")

    def test_negative_raises(self):
        from mcp_linkedin_server.config.loaders import positive_int

        with pytest.raises(argparse.ArgumentTypeError, match="positive"):
            positive_int("-1")


# ── is_interactive_environment ─────────────────────────────────────────


class TestIsInteractive:
    def test_returns_bool(self):
        from mcp_linkedin_server.config.loaders import is_interactive_environment

        assert isinstance(is_interactive_environment(), bool)

    def test_non_tty_returns_false(self, monkeypatch):
        from mcp_linkedin_server.config.loaders import is_interactive_environment

        monkeypatch.setattr("sys.stdin", io.StringIO())
        assert is_interactive_environment() is False

    def test_no_isatty_returns_false(self, monkeypatch):
        from mcp_linkedin_server.config.loaders import is_interactive_environment

        class NoTTY:
            pass

        monkeypatch.setattr("sys.stdin", NoTTY())
        assert is_interactive_environment() is False
