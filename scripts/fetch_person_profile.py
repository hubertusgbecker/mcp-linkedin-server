#!/usr/bin/env python3
"""Fetch and summarize a LinkedIn profile via mcp-use.

Usage:  uv run scripts/fetch_person_profile.py [username]
Default username: hubertusbecker
"""

import asyncio
import os
import sys

os.environ["MCP_USE_ANONYMIZED_TELEMETRY"] = "false"

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from mcp_use import MCPAgent, MCPClient

# Project root is one level up from scripts/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _make_client() -> MCPClient:
    return MCPClient({
        "mcpServers": {
            "linkedin": {
                "command": "uv",
                "args": ["run", "--directory", PROJECT_ROOT, "-m", "linkedin_mcp_server"],
            }
        }
    })


def _make_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=os.environ.get("OPENAI_MODEL", "gpt-5-mini"),
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_REVERSE_PROXY"),
    )


async def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "hubertusbecker"

    client = _make_client()
    agent = MCPAgent(llm=_make_llm(), client=client, max_steps=10, verbose=True)

    try:
        result = await agent.run(
            f"Get the full LinkedIn profile for '{username}'. "
            "Return a structured summary with name, headline, location, about, "
            "experiences, and education."
        )
        print("\n--- RESULT ---")
        print(result)
    finally:
        await client.close_all_sessions()


if __name__ == "__main__":
    asyncio.run(main())
