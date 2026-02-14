#!/usr/bin/env python3
"""Fetch recent posts from a LinkedIn company page via FastMCP client.

Usage:  uv run scripts/fetch_company_posts.py [company_name] [limit]
Defaults: company=bosch, limit=5
"""

import sys

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
        args=["run", "--directory", PROJECT_ROOT, "-m", "mcp_linkedin_server"],
    )
    return Client(transport)


async def main():
    company = sys.argv[1] if len(sys.argv) > 1 else "bosch"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    async with _make_client() as client:
        result = await client.call_tool(
            "get_company_posts", {"company_name": company, "limit": limit}
        )
        print("\n--- RESULT ---")
        for item in result.content:
            if hasattr(item, "text"):
                try:
                    print(json.dumps(json.loads(item.text), indent=2))
                except (json.JSONDecodeError, TypeError):
                    print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
