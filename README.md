# MCP LinkedIn Server

An improved fork of [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server). This fork adds **4 new tools**, totaling **10 MCP tools** for comprehensive LinkedIn automation — from profile research and job discovery to real-time notifications, full post extraction, and profile analytics.

<p align="left">
  <a href="https://github.com/hubertusgbecker/mcp-linkedin-server" target="_blank"><img src="https://img.shields.io/badge/repo-hubertusgbecker%2Fmcp--linkedin--server-blue" alt="GitHub"></a>
  <a href="https://github.com/hubertusgbecker/mcp-linkedin-server/blob/main/LICENSE" target="_blank"><img src="https://img.shields.io/badge/License-Apache%202.0-brightgreen?labelColor=32383f" alt="License"></a>
</p>

## What's Improved Over the Original

| Area | Details |
|------|---------|
| **+4 New tools** | `get_notifications`, `get_post_content`, `get_company_posts`, `get_profile_analytics` — none of these exist in the upstream server |
| **Author resolution** | Notifications resolve each author's LinkedIn username from DOM aria-labels, so you can immediately look up their profile |
| **Post URL linking** | Every notification includes a direct `post_url` you can pass straight into `get_post_content` for the full text |
| **Full post extraction** | Retrieve the complete, non-truncated text of any LinkedIn post along with engagement metrics |
| **Profile analytics** | Monitor your own LinkedIn performance — profile views, post impressions, search appearances, follower count |
| **Improved error handling** | Structured error responses with rate-limit detection, captcha handling, and authentication validation |

## Tools

### People & Companies (upstream)

#### `get_person_profile`

Get a person's full LinkedIn profile by their username. Scrapes the public-facing profile page and returns structured data covering their entire professional background.

| Parameter | Type | Description |
|-----------|------|-------------|
| `linkedin_username` | `str` | URL slug after `linkedin.com/in/` (e.g. `"williamhgates"`, `"satyanadella"`) |

**Returns:** name, location, about section, open-to-work status, current company & job title, full work history (position, company, dates, duration, description), education history, interests (companies, groups, influencers), accomplishments (certifications, publications), and contact details (email, phone, website, Twitter, birthday).

#### `get_company_profile`

Get a company's full LinkedIn profile by its URL slug. Scrapes the "About" page for organizational details, employee highlights, and affiliated entities.

| Parameter | Type | Description |
|-----------|------|-------------|
| `company_name` | `str` | URL slug after `linkedin.com/company/` (e.g. `"anthropic"`, `"docker"`) |

**Returns:** company name, about section, website, phone, headquarters, founded year, industry, company type, size, specialties, headcount, showcase pages, affiliated companies, and featured employees with their LinkedIn URLs.

#### `get_company_posts`

Get recent posts from a company's LinkedIn feed with engagement metrics and media.

| Parameter | Type | Description |
|-----------|------|-------------|
| `company_name` | `str` | URL slug after `linkedin.com/company/` (e.g. `"anthropic"`) |

**Returns:** list of posts with text content, posted time, reactions count, comments count, reposts count, and image URLs.

### Jobs (upstream)

#### `search_jobs`

Search for job postings on LinkedIn by keywords and optional location. Returns a list of job URLs — pass each job ID to `get_job_details` for full information.

| Parameter | Type | Description |
|-----------|------|-------------|
| `keywords` | `str` | Search query (e.g. `"software engineer"`, `"data scientist python"`) |
| `location` | `str \| null` | Geographic filter (e.g. `"Germany"`, `"Remote"`). Optional. |
| `limit` | `int` | Max results to return (default: 25) |

**Returns:** list of LinkedIn job posting URLs and total count.

#### `get_job_details`

Get full details of a specific LinkedIn job posting including the complete description, requirements, and benefits.

| Parameter | Type | Description |
|-----------|------|-------------|
| `job_id` | `str` | Numeric job ID from `linkedin.com/jobs/view/{job_id}/` |

**Returns:** title, company, location, posted date, applicant count, full job description, seniority level, employment type, job function, industries, direct LinkedIn URL, and benefits.

### Notifications & Posts (fork)

#### `get_notifications`

Get recent notifications from the logged-in user's LinkedIn feed. Resolves each author's LinkedIn username from the page DOM so you can immediately look up their profile. Each notification includes a `post_url` that can be passed directly to `get_post_content`.

| Parameter | Type | Description |
|-----------|------|-------------|
| `limit` | `int` | Max notifications to return (default: 10, max: 50) |

**Returns:** list of notifications, each with: author name, `linkedin_username` (resolved from DOM), action type (`"posted"`, `"reposted"`, `"commented on your post"`, etc.), preview text, `post_url` (passable to `get_post_content`), relative timestamp, numeric minutes-ago, and read/unread status.

#### `get_post_content`

Get the full content of any LinkedIn post by URL. Navigates to the post page and extracts the complete (non-truncated) text, author information, and engagement metrics. Use after `get_notifications` to read the full text of truncated notification previews.

| Parameter | Type | Description |
|-----------|------|-------------|
| `post_url` | `str` | Full LinkedIn post URL (activity URN or slug format) |

**Returns:** full post body text, author name, `linkedin_username` (extracted from author profile link), author headline, relative timestamp, reactions count, comments count, and reposts count.

### Analytics (fork)

#### `get_profile_analytics`

Get analytics from the logged-in user's own LinkedIn dashboard. No parameters needed — always returns data for the currently authenticated account.

**Returns:** profile views (past 90 days), post impressions (past 7 days), search appearances (previous week), follower count, weekly posts count, and weekly comments count.

### Session Management

#### `close_session`

Close the LinkedIn browser session and release all resources. Shuts down the Patchright browser, saves cookies for future sessions, and frees memory. The browser will re-launch automatically on the next tool call.

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
        "hubertusgbecker/mcp-linkedin-server:latest"
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
  hubertusgbecker/mcp-linkedin-server:latest \
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

1. Download the [DXT extension](https://github.com/hubertusgbecker/mcp-linkedin-server/releases/latest)
2. Double-click to install into Claude Desktop
3. Create a session: `uvx linkedin-scraper-mcp --get-session`

> Sessions may expire. Run `uvx linkedin-scraper-mcp --get-session` again if authentication fails.

<details>
<summary><b>Troubleshooting</b></summary>

**First-time setup timeout:**

- Claude Desktop has a ~60 second connection timeout
- If the Docker image is not cached, the pull may exceed this
- Fix: pre-pull the image before first use: `docker pull hubertusgbecker/mcp-linkedin-server:latest`
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
cd mcp-linkedin-server

# Install dependencies
uv sync
uv sync --group dev

# Install Patchright browser
uv run patchright install chromium

# Install pre-commit hooks
uv run pre-commit install

# Create a session (first time only)
uv run -m mcp_linkedin_server --get-session

# Start the server
uv run -m mcp_linkedin_server
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
uv run -m mcp_linkedin_server --transport streamable-http --host 127.0.0.1 --port 8000 --path /mcp
```

**Claude Desktop configuration:**

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "uv",
      "args": ["--directory", "/path/to/mcp-linkedin-server", "run", "-m", "mcp_linkedin_server"]
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
