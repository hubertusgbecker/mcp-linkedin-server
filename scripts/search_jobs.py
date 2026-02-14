#!/usr/bin/env python3
"""Search for LinkedIn jobs via mcp-use.

Usage:  uv run scripts/search_jobs.py [keywords] [location] [limit]
Defaults: keywords="AI Engineer", location="Germany", limit=10
"""

import asyncio
import json
import os
import sys

os.environ["MCP_USE_ANONYMIZED_TELEMETRY"] = "false"

from dotenv import load_dotenv
from mcp_use import MCPClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


async def main():
    keywords = sys.argv[1] if len(sys.argv) > 1 else "AI Engineer"
    location = sys.argv[2] if len(sys.argv) > 2 else "Germany"
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 10

    client = MCPClient(
        {
            "mcpServers": {
                "linkedin": {
                    "command": "uv",
                    "args": [
                        "run",
                        "--directory",
                        PROJECT_ROOT,
                        "-m",
                        "linkedin_mcp_server",
                    ],
                }
            }
        }
    )

    try:
        session = await client.create_session("linkedin")
        args = {"keywords": keywords, "limit": limit}
        if location:
            args["location"] = location
        result = await session.call_tool("search_jobs", args)
        print("\n--- RESULT ---")
        for item in result.content:
            if hasattr(item, "text"):
                try:
                    print(json.dumps(json.loads(item.text), indent=2))
                except (json.JSONDecodeError, TypeError):
                    print(item.text)
    finally:
        await client.close_all_sessions()


if __name__ == "__main__":
    asyncio.run(main())
