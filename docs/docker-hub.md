# MCP LinkedIn Server

A Model Context Protocol (MCP) server that connects AI assistants to LinkedIn. Access profiles, companies, jobs, notifications, full post content, and profile analytics through a Docker container.

## Features

- **Profile Access**: Get detailed LinkedIn profile information
- **Company Profiles**: Extract comprehensive company data including posts
- **Job Details**: Retrieve job posting information and search jobs
- **Notifications**: Get recent notifications with author usernames and post URLs
- **Post Content**: Extract full (non-truncated) text from any LinkedIn post
- **Profile Analytics**: Monitor profile views, impressions, search appearances, followers

## Quick Start

Create a browser profile locally, then mount it into Docker.

**Step 1: Create profile using uvx (one-time setup)**

```bash
uvx mcp-linkedin-server --get-session
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

> **Note:** Docker containers don't have a display server, so you can't use the `--get-session` command in Docker. Create a profile on your host first.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `USER_DATA_DIR` | `~/.linkedin-mcp/profile` | Path to persistent browser profile directory |
| `LOG_LEVEL` | `WARNING` | Logging level: DEBUG, INFO, WARNING, ERROR |
| `TIMEOUT` | `5000` | Browser timeout in milliseconds |
| `USER_AGENT` | - | Custom browser user agent |
| `TRANSPORT` | `stdio` | Transport mode: stdio, streamable-http |
| `HOST` | `127.0.0.1` | HTTP server host (for streamable-http transport) |
| `PORT` | `8000` | HTTP server port (for streamable-http transport) |
| `HTTP_PATH` | `/mcp` | HTTP server path (for streamable-http transport) |
| `SLOW_MO` | `0` | Delay between browser actions in ms (debugging) |
| `VIEWPORT` | `1280x720` | Browser viewport size as WIDTHxHEIGHT |
| `CHROME_PATH` | - | Path to Chrome/Chromium executable (rarely needed in Docker) |

**Example with custom timeout:**

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "~/.linkedin-mcp:/home/pwuser/.linkedin-mcp",
        "-e", "TIMEOUT=10000",
        "hubertusgbecker/mcp-linkedin-server"
      ]
    }
  }
}
```

## Repository

- **Source**: <https://github.com/hubertusgbecker/mcp-linkedin-server>
- **License**: Apache 2.0
