#!/usr/bin/env python3
"""Fetch and summarize a LinkedIn profile via FastMCP client + OpenAI.

Usage:  uv run scripts/fetch_person_profile.py [username]
Default username: hubertusbecker

Uses the OpenAI API directly (no langchain) together with FastMCP client
to call MCP tools and then summarize the raw profile data via an LLM.
"""

import asyncio
import os
import sys

from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))


def _make_client() -> Client:
    transport = StdioTransport(
        command="uv",
        args=["run", "--directory", PROJECT_ROOT, "-m", "linkedin_mcp_server"],
    )
    return Client(transport)


def _make_llm() -> AsyncOpenAI:
    return AsyncOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY", "no-key"),
        base_url=os.environ.get("OPENAI_REVERSE_PROXY"),
    )


async def main():
    username = sys.argv[1] if len(sys.argv) > 1 else "hubertusbecker"

    async with _make_client() as mcp:
        # Step 1: Fetch the raw profile via MCP tool
        result = await mcp.call_tool(
            "get_person_profile", {"linkedin_username": username}
        )
        raw_text = "\n".join(item.text for item in result.content if hasattr(item, "text"))

        # Step 2: Summarize with an LLM
        llm = _make_llm()
        model = os.environ.get("OPENAI_MODEL", "gpt-5-mini")
        response = await llm.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. Summarize the following "
                        "LinkedIn profile data into a structured overview with "
                        "name, headline, location, about, experiences, and education."
                    ),
                },
                {"role": "user", "content": raw_text},
            ],
        )
        print("\n--- RESULT ---")
        print(response.choices[0].message.content)


if __name__ == "__main__":
    asyncio.run(main())
