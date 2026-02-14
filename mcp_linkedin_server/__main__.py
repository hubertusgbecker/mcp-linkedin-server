#!/usr/bin/env python3
"""Entry point for mcp-linkedin-server command."""

import sys

sys.stderr.write("[mcp-linkedin-server] __main__.py: loading...\n")
sys.stderr.flush()

from mcp_linkedin_server.cli_main import main

sys.stderr.write("[mcp-linkedin-server] __main__.py: imported, calling main()\n")
sys.stderr.flush()

if __name__ == "__main__":
    main()
