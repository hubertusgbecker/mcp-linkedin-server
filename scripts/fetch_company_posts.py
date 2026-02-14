#!/usr/bin/env python3
"""Fetch recent posts from a LinkedIn company page via mcp-use.

Usage:  uv run scripts/fetch_company_posts.py [company_name] [limit]
Defaults: company=bosch, limit=5
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
    company = sys.argv[1] if len(sys.argv) > 1 else "bosch"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5

    client = MCPClient({
        "mcpServers": {
            "linkedin": {
                "command": "uv",
                "args": ["run", "--directory", PROJECT_ROOT, "-m", "linkedin_mcp_server"],
            }
        }
    })

    try:
        session = await client.create_session("linkedin")
        result = await session.call_tool(
            "get_company_posts", {"company_name": company, "limit": limit}
        )
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
