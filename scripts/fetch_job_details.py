#!/usr/bin/env python3
"""Fetch LinkedIn job posting details via FastMCP client.

Usage:  uv run scripts/fetch_job_details.py [job_id]
Default job_id: 4252026496
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
    job_id = sys.argv[1] if len(sys.argv) > 1 else "4252026496"

    async with _make_client() as client:
        result = await client.call_tool("get_job_details", {"job_id": job_id})
        print("\n--- RESULT ---")
        for item in result.content:
            if hasattr(item, "text"):
                try:
                    print(json.dumps(json.loads(item.text), indent=2))
                except (json.JSONDecodeError, TypeError):
                    print(item.text)


if __name__ == "__main__":
    asyncio.run(main())
