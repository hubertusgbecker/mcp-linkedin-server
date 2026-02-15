"""Tests for authentication: profile_exists, get_authentication_source, clear_profile."""

import pytest

from mcp_linkedin_server.authentication import clear_profile, get_authentication_source
from mcp_linkedin_server.drivers.browser import profile_exists
from mcp_linkedin_server.exceptions import CredentialsNotFoundError


# ── profile_exists ─────────────────────────────────────────────────────
# Note: profile_exists lives in drivers.browser but is tested here alongside
# its primary consumer (authentication). The browser_driver tests cover the
# same function from the driver perspective; conftest's autouse fixtures
# ensure isolation.


class TestProfileExists:
    def test_missing_dir(self, tmp_path):
        assert profile_exists(tmp_path / "nonexistent") is False

    def test_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert profile_exists(empty) is False

    def test_non_empty_dir(self, profile_dir):
        assert profile_exists(profile_dir) is True

    def test_file_path(self, tmp_path):
        f = tmp_path / "not_a_dir"
        f.write_text("data")
        assert profile_exists(f) is False


# ── get_authentication_source ──────────────────────────────────────────


class TestGetAuthenticationSource:
    def test_returns_true_when_profile_exists(self, profile_dir, monkeypatch):
        monkeypatch.setattr(
            "mcp_linkedin_server.authentication.profile_exists", lambda _dir=None: True
        )
        assert get_authentication_source() is True

    def test_raises_when_no_profile(self, monkeypatch):
        monkeypatch.setattr(
            "mcp_linkedin_server.authentication.profile_exists", lambda _dir=None: False
        )
        with pytest.raises(CredentialsNotFoundError):
            get_authentication_source()

    def test_error_includes_get_session_hint(self, monkeypatch):
        monkeypatch.setattr(
            "mcp_linkedin_server.authentication.profile_exists", lambda _dir=None: False
        )
        with pytest.raises(CredentialsNotFoundError, match="--get-session"):
            get_authentication_source()

    def test_error_includes_docker_instructions(self, monkeypatch):
        monkeypatch.setattr(
            "mcp_linkedin_server.authentication.profile_exists", lambda _dir=None: False
        )
        with pytest.raises(CredentialsNotFoundError, match="Docker"):
            get_authentication_source()


# ── clear_profile ──────────────────────────────────────────────────────


class TestClearProfile:
    def test_removes_existing_dir(self, profile_dir):
        assert profile_dir.exists()
        result = clear_profile(profile_dir)
        assert result is True
        assert not profile_dir.exists()

    def test_nonexistent_dir_returns_true(self, tmp_path):
        result = clear_profile(tmp_path / "does_not_exist")
        assert result is True

    def test_default_profile_uses_get_profile_dir(self, monkeypatch, tmp_path):
        """clear_profile() with no arg uses get_profile_dir()."""
        profile = tmp_path / "default"
        profile.mkdir()
        (profile / "data").write_text("stuff")
        monkeypatch.setattr(
            "mcp_linkedin_server.authentication.get_profile_dir", lambda: profile
        )
        result = clear_profile()
        assert result is True
        assert not profile.exists()

    def test_permission_error_returns_false(self, monkeypatch, tmp_path):
        """OSError during rmtree should return False."""
        profile = tmp_path / "locked"
        profile.mkdir()
        (profile / "data").write_text("x")

        def mock_rmtree(path, *a, **kw):
            raise OSError("Permission denied")

        monkeypatch.setattr("shutil.rmtree", mock_rmtree)
        result = clear_profile(profile)
        assert result is False
