# AGENTS.md

> Canonical guidance for all AI coding agents (Claude Code, GitHub Copilot, Cursor, Gemini Code Assist, etc.) working in this repository. If your tool reads `CLAUDE.md`, that file redirects here.

---

## Quick Reference

| Action | Command |
|---|---|
| Install deps | `uv sync` |
| Install dev deps | `uv sync --group dev` |
| Install browser | `uv run patchright install chromium` |
| Run server (local) | `uv run -m mcp_linkedin_server --no-headless` |
| Run via uvx (PyPI) | `uvx mcp-linkedin-server` |
| Run in Docker | `docker run -it --rm -v ~/.linkedin-mcp:/home/pwuser/.linkedin-mcp hubertusgbecker/mcp-linkedin-server:latest` |
| Lint | `uv run ruff check .` (auto-fix: `--fix`) |
| Format | `uv run ruff format .` |
| Type check | `uv run ty check` |
| Test | `uv run pytest` (with coverage: `--cov`) |
| Pre-commit | `uv run pre-commit run --all-files` |
| Build Docker | `docker build -t mcp-linkedin-server .` |
| Get session | `uvx mcp-linkedin-server --get-session` |
| Bump version | `uv version --bump patch` (or `minor` / `major`) |

---

## Project Overview

**MCP LinkedIn Server** — a Model Context Protocol server enabling AI assistants to interact with LinkedIn through web scraping. Built on FastMCP and Patchright (anti-detection Playwright fork).

- **Language:** Python 3.12+
- **Package manager:** [uv](https://docs.astral.sh/uv/)
- **PyPI package:** `mcp-linkedin-server` (entry points: `mcp-linkedin-server`, `linkedin-mcp-server`, `linkedin-scraper-mcp`)
- **Python package:** `mcp_linkedin_server`
- **License:** Apache-2.0
- **Repository:** <https://github.com/hubertusgbecker/mcp-linkedin-server>

---

## Architecture

```
mcp_linkedin_server/
├── __init__.py          # Package metadata, version from importlib
├── __main__.py          # `python -m mcp_linkedin_server` entry
├── cli_main.py          # CLI argument parsing and orchestration (main entry point)
├── cli.py               # Interactive CLI helpers (session wizard)
├── server.py            # FastMCP server setup and tool registration
├── setup.py             # Browser initialization, lifespan management
├── authentication.py    # LinkedIn browser-profile validation
├── error_handler.py     # Centralized error handling and retry logic
├── exceptions.py        # Custom exception hierarchy
├── logging_config.py    # Structured logging configuration
├── config/
│   ├── loaders.py       # Layered config loading (CLI → env → defaults)
│   ├── schema.py        # Config dataclasses and validation
│   ├── providers.py     # Configuration provider abstraction
│   ├── secrets.py       # Secure credential handling
│   └── messages.py      # User-facing message constants
├── drivers/
│   └── browser.py       # Patchright browser lifecycle (singleton)
└── tools/
    ├── person.py        # get_person_profile
    ├── company.py       # get_company_profile, get_company_posts
    ├── job.py           # get_job_details, search_jobs
    ├── notifications.py # get_notifications
    ├── post_content.py  # get_post_content
    └── analytics.py     # get_recommended_jobs, close_session
```

### Startup Sequence

1. **CLI parsing** (`cli_main.py`) — Reads args, loads config
2. **Authentication** (`authentication.py`) — Validates browser profile at `~/.linkedin-mcp/profile/`
3. **Server** (`server.py`) — Registers tools on a FastMCP instance, starts transport

### Transport Modes

- **stdio** (default) — Standard I/O for local MCP clients (Claude Desktop, etc.)
- **streamable-http** — HTTP server for web-based MCP clients

### Key Patterns

- **Singleton browser** — One Patchright browser instance shared across all tool invocations
- **Lazy initialization** — Browser launches on first tool call (unless `--no-lazy-init`)
- **Persistent profile** — Browser state survives restarts via `~/.linkedin-mcp/profile/`
- **Lifespan management** — FastMCP lifespan context handles browser setup/teardown

---

## Available MCP Tools

| Tool | Module | Description |
|---|---|---|
| `get_person_profile` | `tools/person.py` | Profile with contacts, interests, experiences, education |
| `get_company_profile` | `tools/company.py` | Company info with employees, affiliates, showcase pages |
| `get_company_posts` | `tools/company.py` | Recent posts from company feed with reactions/comments |
| `get_job_details` | `tools/job.py` | Job posting details including description and benefits |
| `search_jobs` | `tools/job.py` | Search jobs by keywords and location |
| `get_notifications` | `tools/notifications.py` | Notification feed with author usernames, actions, post URLs |
| `get_post_content` | `tools/post_content.py` | Full post text, author, headline, engagement metrics |
| `get_recommended_jobs` | `tools/analytics.py` | Recommended jobs from LinkedIn feed |
| `close_session` | `tools/analytics.py` | Close browser session and clean up resources |

---

## Key Dependencies

| Package | Import | Purpose |
|---|---|---|
| `fastmcp` | `fastmcp` | MCP server framework |
| `linkedin-scraper-patchright` | `linkedin_scraper` | LinkedIn web scraping (v3) |
| `patchright` | `patchright` | Anti-detection browser automation |
| `python-dotenv` | `dotenv` | Environment variable loading |
| `inquirer` | `inquirer` | Interactive CLI prompts |
| `pyperclip` | `pyperclip` | Clipboard access for session sharing |

> **Important:** `from linkedin_scraper import ...` refers to the external `linkedin-scraper-patchright` PyPI package. Never rename these imports.

---

## Testing

- **Framework:** pytest with `pytest-asyncio` (mode: `auto`)
- **Test directory:** `tests/` — 14 test modules, 175+ tests
- **Parallelism:** `pytest-xdist` available (`-n auto`)

```bash
uv run pytest                       # Run all tests
uv run pytest --cov                 # With coverage
uv run pytest -x --tb=short        # Stop on first failure, short tracebacks
uv run pytest tests/test_server.py  # Single module
```

### Test Conventions

- Unit tests mock browser interactions — no real LinkedIn calls
- Fixtures in `tests/conftest.py` provide common mocks
- All async tests use `@pytest.mark.asyncio` (auto mode means no explicit marker needed)

---

## Code Quality

```bash
uv run ruff check .               # Lint (auto-fix: --fix)
uv run ruff format .              # Format
uv run ty check                   # Type check (using ty, not mypy)
uv run pre-commit run --all-files # All hooks
```

---

## Release Process

**Only manual step:** `uv version --bump patch` (or `minor` / `major`).

The GitHub Actions release workflow (`.github/workflows/release.yml`) automatically:
1. Updates `manifest.json` and `docker-compose.yml` version strings
2. Creates git tag
3. Builds and pushes Docker image to Docker Hub
4. Builds DXT extension for Claude Desktop
5. Creates GitHub release with all assets
6. Publishes to PyPI

After the workflow completes, manually file a PR in the MCP registry to update the version.

---

## Development Workflow

1. Check open issues. If no issue exists, create one using the appropriate issue template.
2. Create a branch from `main`: `feature/<issue-number>-<short-description>`
3. Implement the feature or fix
4. Run tests: `uv run pytest`
5. Run lint/format: `uv run ruff check . && uv run ruff format --check .`
6. Update documentation: `README.md`, `docs/docker-hub.md`, and `AGENTS.md`
7. Create a PR with a concise description
8. Review with AI agents first, then manual review
9. Merge (do **not** squash commits)
10. Delete the branch after merge

### Commit Message Format

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): subject
```

- **Types:** `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`, `ci`
- **Subject:** imperative mood, <50 chars
- **Never** sign commits or PRs with AI agent identifiers

---

## Configuration

### CLI Arguments

| Flag | Description | Default |
|---|---|---|
| `--get-session` | Open browser to create persistent profile | — |
| `--no-headless` | Show browser window | headless |
| `--no-lazy-init` | Initialize browser immediately on startup | lazy |
| `--log-level` | `DEBUG` / `INFO` / `WARNING` / `ERROR` | `WARNING` |
| `--transport` | `stdio` / `streamable-http` | `stdio` |
| `--host` | HTTP server host | `127.0.0.1` |
| `--port` | HTTP server port | `8000` |
| `--path` | HTTP server path | `/mcp` |
| `--timeout` | Browser page timeout (ms) | `5000` |
| `--user-data-dir` | Browser profile directory | `~/.linkedin-mcp/profile` |
| `--chrome-path` | Chrome/Chromium executable path | auto-detect |
| `--clear-session` | Delete stored browser profile | — |

### Environment Variables

Corresponding env vars follow `UPPER_SNAKE_CASE` convention (e.g., `TIMEOUT=10000`, `CHROME_PATH=/path/to/chrome`). See `.env.example`.

### Authentication

Uses a persistent Patchright browser profile at `~/.linkedin-mcp/profile/`. Run `--get-session` to create one via interactive browser login (5 min timeout for 2FA/captcha).

---

## Error Handling

- **Rate limits:** Detected and surfaced with actionable messages
- **Captcha challenges:** User prompted to run `--get-session` to solve manually
- **Session expiry:** Graceful error with re-authentication instructions
- **Custom exceptions:** Defined in `exceptions.py` (`CredentialsNotFoundError`, etc.)

---

## btca

When you need up-to-date information about technologies used in this project, use `btca` to query source repositories directly.

**Available resources:** `fastmcp`, `linkedinScraper`, `patchright`, `pytest`, `ruff`, `ty`, `uv`, `inquirer`, `pythonDotenv`, `pyperclip`, `preCommit`

```bash
btca ask -r <resource> -q "<question>"
btca ask -r fastmcp -r patchright -q "How do I set up browser context with FastMCP tools?"
```
