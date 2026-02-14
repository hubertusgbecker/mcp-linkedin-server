#!/usr/bin/env python3
"""Close the LinkedIn MCP browser session via mcp-use.

Usage:  uv run scripts/close_session.py
"""

import asyncio
import json
import os

os.environ["MCP_USE_ANONYMIZED_TELEMETRY"] = "false"

from dotenv import load_dotenv
from mcp_use import MCPClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


async def main():
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
        result = await session.call_tool("close_session", {})
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
