"""Tests for setup.py: run_profile_creation and run_interactive_setup."""


class TestRunProfileCreation:
    def test_success_with_custom_dir(self, tmp_path, monkeypatch):
        from mcp_linkedin_server.setup import run_profile_creation

        monkeypatch.setattr(
            "mcp_linkedin_server.setup.asyncio.run",
            lambda coro: True,
        )
        result = run_profile_creation(str(tmp_path / "custom"))
        assert result is True

    def test_success_with_default_dir(self, monkeypatch, tmp_path):
        from mcp_linkedin_server.setup import run_profile_creation

        monkeypatch.setattr(
            "mcp_linkedin_server.setup.get_profile_dir", lambda: tmp_path
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.setup.asyncio.run",
            lambda coro: True,
        )
        result = run_profile_creation()
        assert result is True

    def test_failure_returns_false(self, monkeypatch, tmp_path):
        from mcp_linkedin_server.setup import run_profile_creation

        monkeypatch.setattr(
            "mcp_linkedin_server.setup.get_profile_dir", lambda: tmp_path
        )

        def raise_error(coro):
            raise RuntimeError("browser crash")

        monkeypatch.setattr("mcp_linkedin_server.setup.asyncio.run", raise_error)
        result = run_profile_creation()
        assert result is False


class TestRunInteractiveSetup:
    def test_success(self, monkeypatch, tmp_path):
        from mcp_linkedin_server.setup import run_interactive_setup

        monkeypatch.setattr(
            "mcp_linkedin_server.setup.get_profile_dir", lambda: tmp_path
        )
        monkeypatch.setattr(
            "mcp_linkedin_server.setup.asyncio.run",
            lambda coro: True,
        )
        result = run_interactive_setup()
        assert result is True

    def test_failure_returns_false(self, monkeypatch, tmp_path):
        from mcp_linkedin_server.setup import run_interactive_setup

        monkeypatch.setattr(
            "mcp_linkedin_server.setup.get_profile_dir", lambda: tmp_path
        )

        def raise_error(coro):
            raise RuntimeError("login failed")

        monkeypatch.setattr("mcp_linkedin_server.setup.asyncio.run", raise_error)
        result = run_interactive_setup()
        assert result is False
