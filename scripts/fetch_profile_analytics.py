#!/usr/bin/env python3
"""Fetch your own LinkedIn profile analytics dashboard via FastMCP client.

Usage:  uv run scripts/fetch_profile_analytics.py

Returns profile views, post impressions, search appearances,
followers, and weekly sharing activity.
"""

import asyncio
import json
import os

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _make_client() -> Client:
    transport = StdioTransport(
        command="uv",
        args=["run", "--directory", PROJECT_ROOT, "-m", "linkedin_mcp_server"],
    )
    return Client(transport)


async def main():
    async with _make_client() as client:
        result = await client.call_tool("get_profile_analytics", {})
        print("\n--- RESULT ---")
        for item in result.content:
            if hasattr(item, "text"):
                try:
                    print(json.dumps(json.loads(item.text), indent=2))
                except (json.JSONDecodeError, TypeError):
                    print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
