# n8n Workflows for LinkedIn MCP Server

Pre-built [n8n](https://n8n.io/) workflow templates that consume the LinkedIn MCP Server API via JSON-RPC over HTTP.

## Prerequisites

1. **Start the MCP server** in streamable-http mode:

   ```bash
   # Local
   uv run -m mcp_linkedin_server --no-headless --transport streamable-http

   # Docker (runs on port 8100)
   docker compose up
   ```

   Default endpoint: `http://localhost:8000/mcp` (local) or `http://localhost:8100/mcp` (Docker Compose)

2. **Authenticate** — ensure you have a valid browser profile:

   ```bash
   uv run -m mcp_linkedin_server --get-session
   ```

3. **n8n** running locally or in the cloud.

## Importing Workflows

1. Open n8n → **Workflows** → **Import from file**
2. Select any `.json` file from this directory
3. Update the HTTP Request node URL if your server is not at `http://localhost:8000/mcp`

## Available Workflows

### Single-Tool Workflows

| Workflow | File | Description |
|---|---|---|
| Get Person Profile | `get_person_profile.json` | Fetch a LinkedIn user's full profile by username |
| Get Company Profile | `get_company_profile.json` | Fetch company info, employees, affiliates |
| Get Company Posts | `get_company_posts.json` | Fetch recent posts from a company feed |
| Search Jobs | `search_jobs.json` | Search job listings by keywords and location |
| Get Job Details | `get_job_details.json` | Fetch full details for a specific job posting |
| Get Notifications | `get_notifications.json` | Fetch your LinkedIn notification feed |
| Get Post Content | `get_post_content.json` | Fetch full content of a specific LinkedIn post |
| Get Profile Analytics | `get_profile_analytics.json` | Fetch your profile view/search analytics |
| Close Session | `close_session.json` | Gracefully close the browser session |

### Pipeline Workflows

| Workflow | File | Description |
|---|---|---|
| Search → Details | `search_jobs_then_get_details.json` | Search jobs, then fetch details for each result |
| Notifications → Posts | `notifications_then_post_content.json` | Get notifications, filter those with post URLs, fetch each post's content |

## How It Works

Each workflow sends a JSON-RPC request to the MCP server:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "get_person_profile",
    "arguments": {
      "linkedin_username": "satyanadella"
    }
  }
}
```

The response contains the tool result in `result.content[0].text` (JSON string).

## Customization

- **Server URL**: Update the HTTP Request node's URL field if not using the default `http://localhost:8000/mcp`
- **Timeout**: Scraping can take 10-60s per page. The HTTP Request nodes have generous timeouts configured.
- **Parameters**: Edit the "Set Parameters" node at the start of each workflow to change inputs.

## MCP Tool Reference

| Tool | Parameters | Description |
|---|---|---|
| `get_person_profile` | `linkedin_username` (required) | Profile with contacts, experiences, education |
| `get_company_profile` | `company_name` (required) | Company info with employees, affiliates |
| `get_company_posts` | `company_name` (required), `limit` (default: 10) | Recent company feed posts |
| `get_job_details` | `job_id` (required) | Job posting details |
| `search_jobs` | `keywords` (required), `location`, `limit` (default: 25) | Search job listings |
| `get_notifications` | `limit` (default: 10) | Notification feed |
| `get_post_content` | `post_url` (required) | Full post text and engagement metrics |
| `get_profile_analytics` | _(none)_ | Profile view/search/appearance stats |
| `close_session` | _(none)_ | Close browser and clean up resources |
