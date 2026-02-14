# LinkedIn MCP Server (Fork)

Fork of [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) with significant additions including notifications with author username resolution, profile analytics dashboard scraping, and improved error handling.

<p align="left">
  <a href="https://github.com/stickerdaniel/linkedin-mcp-server" target="_blank"><img src="https://img.shields.io/badge/upstream-stickerdaniel%2Flinkedin--mcp--server-blue" alt="Upstream"></a>
  <a href="https://github.com/stickerdaniel/linkedin-mcp-server/blob/main/LICENSE" target="_blank"><img src="https://img.shields.io/badge/License-Apache%202.0-brightgreen?labelColor=32383f" alt="License"></a>
</p>

## What Changed in This Fork

This fork extends the original server with two new tool categories and various fixes:

- **Notifications tool** -- Scrapes linkedin.com/notifications/ and returns structured notification data including author names, LinkedIn usernames (resolved from DOM aria-labels), action types, timestamps, and read/unread status.
- **Profile analytics tool** -- Scrapes linkedin.com/dashboard/ for the logged-in user's own metrics: profile views, post impressions, search appearances, follower count, and weekly sharing activity (posts, comments, reposts, videos, documents, articles).
- **Post content tool** -- Navigates to any LinkedIn post URL and extracts the full (non-truncated) text, author name, author headline, posted time, and engagement metrics (reactions, comments, reposts). Works with post URLs returned by the notifications tool.

## Tools

| Tool | Description | Origin |
|------|-------------|--------|
| `get_person_profile` | Detailed profile info including work history, education, contacts, interests | Upstream |
| `get_company_profile` | Company information including employees, affiliated companies | Upstream |
| `get_company_posts` | Recent posts from a company LinkedIn feed | Upstream |
| `search_jobs` | Search for jobs with keywords and location filters | Upstream |
| `get_job_details` | Detailed information about a specific job posting | Upstream |
| `get_notifications` | Recent notifications with author LinkedIn usernames, actions, timestamps | Fork |
| `get_post_content` | Full post text, author, headline, and engagement metrics from any post URL | Fork |
| `get_profile_analytics` | Dashboard analytics: profile views, impressions, search appearances, followers | Fork |
| `close_session` | Close browser session and clean up resources | Upstream |

> **Warning:** The browser profile at `~/.linkedin-mcp/profile/` contains sensitive authentication data. Keep it secure and do not share it.

> **Important:** This version uses [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright-python) with persistent browser profiles instead of Playwright with session files. Old `session.json` files and `LINKEDIN_COOKIE` env vars are no longer supported. Run `--get-session` again to create a new profile.

---

## Installation Methods

### uvx Setup (Recommended)

**Prerequisites:** [uv](https://docs.astral.sh/uv/) installed, plus Patchright browser: `uvx patchright install chromium`

**Step 1: Create a session (first time only)**

```bash
uvx linkedin-scraper-mcp --get-session
```

This opens a browser for you to log in manually (5 minute timeout for 2FA, captcha, etc.). The browser profile is saved to `~/.linkedin-mcp/profile/`.

**Step 2: Run the server**

```bash
uvx linkedin-scraper-mcp
```

> Sessions may expire over time. If you encounter authentication issues, run `uvx linkedin-scraper-mcp --get-session` again.

**Client configuration:**

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "uvx",
      "args": ["linkedin-scraper-mcp"]
    }
  }
}
```

<details>
<summary><b>Configuration</b></summary>

**Transport modes:**

- **Default (stdio)** -- Standard communication for local MCP servers
- **Streamable HTTP** -- For web-based MCP server

**CLI options:**

- `--get-session` -- Open browser to log in and save persistent profile
- `--no-headless` -- Show browser window (useful for debugging)
- `--log-level {DEBUG,INFO,WARNING,ERROR}` -- Set logging level (default: WARNING)
- `--transport {stdio,streamable-http}` -- Set transport mode
- `--host HOST` -- HTTP server host (default: 127.0.0.1)
- `--port PORT` -- HTTP server port (default: 8000)
- `--path PATH` -- HTTP server path (default: /mcp)
- `--clear-session` -- Clear stored LinkedIn browser profile
- `--timeout MS` -- Browser timeout for page operations in milliseconds (default: 5000)
- `--user-data-dir PATH` -- Path to persistent browser profile directory (default: ~/.linkedin-mcp/profile)
- `--chrome-path PATH` -- Path to Chrome/Chromium executable

**HTTP mode example:**

```bash
uvx linkedin-scraper-mcp --transport streamable-http --host 127.0.0.1 --port 8080 --path /mcp
```

</details>

<details>
<summary><b>Troubleshooting</b></summary>

**Installation issues:**

- Ensure uv is installed: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Check uv version: `uv --version` (should be 0.4.0 or higher)

**Session issues:**

- Browser profile is stored at `~/.linkedin-mcp/profile/`
- Make sure you have only one active LinkedIn session at a time

**Login issues:**

- LinkedIn may require a login confirmation in the LinkedIn mobile app for `--get-session`
- Captcha challenges can occur after frequent logins. Run `uvx linkedin-scraper-mcp --get-session` to solve them manually in the browser.

**Timeout issues:**

- If pages fail to load, try `--timeout 10000`
- Slow connections may need 15000-30000ms
- Environment variable alternative: `TIMEOUT=10000`

**Custom Chrome path:**

- Use `--chrome-path /path/to/chrome` for non-standard installations
- Environment variable alternative: `CHROME_PATH=/path/to/chrome`

</details>

---

### Docker Setup

**Prerequisites:** [Docker](https://www.docker.com/get-started/) installed and running

Docker runs headless, so create a browser profile locally first and mount it into the container.

**Step 1: Create profile using uvx (one-time setup)**

```bash
uvx linkedin-scraper-mcp --get-session
```

**Step 2: Configure Claude Desktop with Docker**

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "docker",
      "args": [
        "run", "--rm", "-i",
        "-v", "~/.linkedin-mcp:/home/pwuser/.linkedin-mcp",
        "stickerdaniel/linkedin-mcp-server:latest"
      ]
    }
  }
}
```

> Sessions may expire over time. If you encounter authentication issues, run `uvx linkedin-scraper-mcp --get-session` again locally.

> Docker containers lack a display server. Create profiles on your host using the uvx setup above and mount them into Docker.

<details>
<summary><b>Configuration</b></summary>

**CLI options (Docker):**

- `--log-level {DEBUG,INFO,WARNING,ERROR}` -- Set logging level (default: WARNING)
- `--transport {stdio,streamable-http}` -- Set transport mode
- `--host HOST` -- HTTP server host (default: 127.0.0.1)
- `--port PORT` -- HTTP server port (default: 8000)
- `--path PATH` -- HTTP server path (default: /mcp)
- `--clear-session` -- Clear stored LinkedIn browser profile
- `--timeout MS` -- Browser timeout in milliseconds (default: 5000)
- `--user-data-dir PATH` -- Path to persistent browser profile directory
- `--chrome-path PATH` -- Path to Chrome/Chromium executable (rarely needed in Docker)

> `--get-session` and `--no-headless` are not available in Docker (no display server). Use uvx to create profiles.

**HTTP mode example:**

```bash
docker run -it --rm \
  -v ~/.linkedin-mcp:/home/pwuser/.linkedin-mcp \
  -p 8080:8080 \
  stickerdaniel/linkedin-mcp-server:latest \
  --transport streamable-http --host 0.0.0.0 --port 8080 --path /mcp
```

</details>

<details>
<summary><b>Troubleshooting</b></summary>

**Docker issues:**

- Make sure Docker is installed and running: `docker ps`

**Login issues:**

- Keep only one active LinkedIn session at a time
- Captcha challenges: run `uvx linkedin-scraper-mcp --get-session` locally to solve them

**Timeout issues:**

- Try `--timeout 10000` for slow pages
- Slow connections may need 15000-30000ms
- Environment variable alternative: `TIMEOUT=10000`

</details>

---

### Claude Desktop DXT Extension

**Prerequisites:** [Claude Desktop](https://claude.ai/download) and [Docker](https://www.docker.com/get-started/) installed and running

1. Download the [DXT extension](https://github.com/stickerdaniel/linkedin-mcp-server/releases/latest)
2. Double-click to install into Claude Desktop
3. Create a session: `uvx linkedin-scraper-mcp --get-session`

> Sessions may expire. Run `uvx linkedin-scraper-mcp --get-session` again if authentication fails.

<details>
<summary><b>Troubleshooting</b></summary>

**First-time setup timeout:**

- Claude Desktop has a ~60 second connection timeout
- If the Docker image is not cached, the pull may exceed this
- Fix: pre-pull the image before first use: `docker pull stickerdaniel/linkedin-mcp-server:latest`
- Then restart Claude Desktop

**Docker issues:**

- Make sure Docker is installed and running: `docker ps`

**Login issues:**

- Keep only one active LinkedIn session at a time
- Captcha challenges: run `uvx linkedin-scraper-mcp --get-session` locally

**Timeout issues:**

- Try `--timeout 10000` for slow pages
- Environment variable alternative: `TIMEOUT=10000`

</details>

---

### Local Setup (Development)

**Prerequisites:** [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/) installed

```bash
# Clone this fork
git clone https://github.com/hubertusgbecker/mcp-linkedin-server
cd linkedin-mcp-server

# Install dependencies
uv sync
uv sync --group dev

# Install Patchright browser
uv run patchright install chromium

# Install pre-commit hooks
uv run pre-commit install

# Create a session (first time only)
uv run -m linkedin_mcp_server --get-session

# Start the server
uv run -m linkedin_mcp_server
```

<details>
<summary><b>Configuration</b></summary>

**CLI options:**

- `--get-session` -- Open browser to log in and save persistent profile
- `--no-headless` -- Show browser window (useful for debugging)
- `--log-level {DEBUG,INFO,WARNING,ERROR}` -- Set logging level (default: WARNING)
- `--transport {stdio,streamable-http}` -- Set transport mode
- `--host HOST` -- HTTP server host (default: 127.0.0.1)
- `--port PORT` -- HTTP server port (default: 8000)
- `--path PATH` -- HTTP server path (default: /mcp)
- `--clear-session` -- Clear stored LinkedIn browser profile
- `--timeout MS` -- Browser timeout in milliseconds (default: 5000)
- `--session-info` -- Check if current session is valid and exit
- `--user-data-dir PATH` -- Path to persistent browser profile directory
- `--slow-mo MS` -- Delay between browser actions in milliseconds (default: 0)
- `--user-agent STRING` -- Custom browser user agent
- `--viewport WxH` -- Browser viewport size (default: 1280x720)
- `--chrome-path PATH` -- Path to Chrome/Chromium executable
- `--help` -- Show help

Most CLI options have environment variable equivalents. See `.env.example` for details.

**HTTP mode example:**

```bash
uv run -m linkedin_mcp_server --transport streamable-http --host 127.0.0.1 --port 8000 --path /mcp
```

**Claude Desktop configuration:**

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "uv",
      "args": ["--directory", "/path/to/linkedin-mcp-server", "run", "-m", "linkedin_mcp_server"]
    }
  }
}
```

</details>

<details>
<summary><b>Troubleshooting</b></summary>

**Login issues:**

- Keep only one active LinkedIn session at a time
- LinkedIn may require confirmation in the mobile app for `--get-session`
- Captcha challenges: `--get-session` opens a browser where you can solve them manually

**Scraping issues:**

- Use `--no-headless` to watch browser actions and debug problems
- Add `--log-level DEBUG` for detailed logging

**Session issues:**

- Profile stored at `~/.linkedin-mcp/profile/`
- Use `--clear-session` to clear the profile and start fresh

**Python/Patchright issues:**

- Check Python version: `python --version` (requires 3.12+)
- Reinstall Patchright: `uv run patchright install chromium`
- Reinstall dependencies: `uv sync --reinstall`

**Timeout issues:**

- Try `--timeout 10000` for slow pages
- Slow connections may need 15000-30000ms
- Environment variable alternative: `TIMEOUT=10000`

**Custom Chrome path:**

- Use `--chrome-path /path/to/chrome`
- Environment variable alternative: `CHROME_PATH=/path/to/chrome`

</details>

---

## Usage Examples

```
Research the background of this candidate https://www.linkedin.com/in/hubertusgbecker/
```

```
Get this company profile for partnership discussions https://www.linkedin.com/company/inframs/
```

```
Suggest improvements for my CV to target this job posting https://www.linkedin.com/jobs/view/4252026496
```

```
What has Anthropic been posting about recently? https://www.linkedin.com/company/anthropic/
```

```
Show me my latest LinkedIn notifications
```

```
Get the full text of this post https://www.linkedin.com/feed/update/urn:li:activity:7428449943742357505/
```

```
How is my LinkedIn profile performing this week?
```

---

## Acknowledgements

Forked from [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server).

Built with [LinkedIn Scraper](https://github.com/joeyism/linkedin_scraper) by [@joeyism](https://github.com/joeyism) and [FastMCP](https://gofastmcp.com/).

Use in accordance with [LinkedIn's Terms of Service](https://www.linkedin.com/legal/user-agreement). Web scraping may violate LinkedIn's terms. This tool is for personal use only.

## License

Apache 2.0
