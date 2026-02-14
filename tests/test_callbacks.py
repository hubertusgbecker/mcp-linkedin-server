"""Tests for MCPContextProgressCallback."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from linkedin_mcp_server.callbacks import MCPContextProgressCallback


@pytest.fixture
def ctx():
    ctx = MagicMock()
    ctx.report_progress = AsyncMock()
    return ctx


class TestMCPContextProgressCallback:
    async def test_on_start(self, ctx):
        cb = MCPContextProgressCallback(ctx)
        await cb.on_start("PersonScraper", "https://linkedin.com/in/test/")
        ctx.report_progress.assert_awaited_once_with(
            progress=0, total=100, message="Starting PersonScraper"
        )

    async def test_on_progress(self, ctx):
        cb = MCPContextProgressCallback(ctx)
        await cb.on_progress("Loading contacts", 42)
        ctx.report_progress.assert_awaited_once_with(
            progress=42, total=100, message="Loading contacts"
        )

    async def test_on_complete(self, ctx):
        cb = MCPContextProgressCallback(ctx)
        await cb.on_complete("PersonScraper", {"name": "test"})
        ctx.report_progress.assert_awaited_once_with(
            progress=100, total=100, message="Complete"
        )

    async def test_full_lifecycle(self, ctx):
        """Simulate a full scrape lifecycle: start → progress → complete."""
        cb = MCPContextProgressCallback(ctx)

        await cb.on_start("CompanyScraper", "https://linkedin.com/company/test/")
        await cb.on_progress("Extracting details", 50)
        await cb.on_complete("CompanyScraper", {})

        assert ctx.report_progress.await_count == 3
