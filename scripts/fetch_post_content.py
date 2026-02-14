#!/usr/bin/env python3
"""Fetch full content of a LinkedIn post via FastMCP client.

Usage:  uv run scripts/fetch_post_content.py <post_url>

The post_url can be:
  - https://www.linkedin.com/feed/update/urn:li:activity:XXXX/
  - A post_url value from get_notifications output
"""

import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _make_client() -> Client:
    transport = StdioTransport(
        command="uv",
        args=["run", "--directory", PROJECT_ROOT, "-m", "mcp_linkedin_server"],
    )
    return Client(transport)


async def main():
    if len(sys.argv) < 2:
        print("Usage: uv run scripts/fetch_post_content.py <post_url>")
        sys.exit(1)

    post_url = sys.argv[1]

    async with _make_client() as client:
        result = await client.call_tool("get_post_content", {"post_url": post_url})
        print("\n--- RESULT ---")
        for item in result.content:
            if hasattr(item, "text"):
                try:
                    print(json.dumps(json.loads(item.text), indent=2))
                except (json.JSONDecodeError, TypeError):
                    print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
