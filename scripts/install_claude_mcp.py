"""
One-shot script to install ProjectMind into Claude Desktop.

Run this script to configure Claude Desktop to use the ProjectMind
MCP server for the current repository.

Usage:
    python scripts/install_claude_mcp.py
"""

import sys
from pathlib import Path

# Add project root to path so we can import projectmind without installing it
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from projectmind.platform.adapters.claude_desktop import install_claude_desktop_config  # noqa: E402

if __name__ == "__main__":
    try:
        install_claude_desktop_config(dry_run=False)
    except Exception as e:
        print(f"Error installing Claude Desktop config: {e}", file=sys.stderr)
        sys.exit(1)
