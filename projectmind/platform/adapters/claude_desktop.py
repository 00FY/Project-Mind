"""
Claude Desktop integration adapter.

Handles:
1. Formatting MCP responses for Claude's expected schema
2. Generating Claude Desktop's ``claude_desktop_config.json`` snippet
3. Installing / updating the config file automatically

Claude Desktop MCP config format:

    {
        "mcpServers": {
            "projectmind": {
                "command": "projectmind",
                "args": ["serve"]
            }
        }
    }

References:
    https://modelcontextprotocol.io/quickstart/user
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from projectmind.platform.adapters.base import AgentAdapter, register_adapter
from projectmind.platform.logging.setup import get_logger

logger = get_logger("adapters.claude_desktop")

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False
    console = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Config path detection
# ---------------------------------------------------------------------------


def _get_claude_config_path() -> Path:
    """Return the platform-specific path to Claude Desktop's config file."""
    import platform
    system = platform.system()

    if system == "Darwin":  # macOS
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "Claude"
            / "claude_desktop_config.json"
        )
    elif system == "Windows":
        appdata = Path(sys.platform == "win32" and __import__("os").environ.get("APPDATA", "") or "")
        return appdata / "Claude" / "claude_desktop_config.json"
    else:  # Linux / other
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


# ---------------------------------------------------------------------------
# Config generation
# ---------------------------------------------------------------------------


def _build_mcp_entry(command: str = "projectmind", args: list[str] | None = None) -> dict[str, Any]:
    """Build the ProjectMind MCP server entry for Claude Desktop config."""
    return {
        "command": command,
        "args": args or ["serve"],
        "description": (
            "ProjectMind — local project intelligence and memory layer. "
            "Provides project-aware context for AI coding tasks."
        ),
    }


def generate_claude_config_snippet() -> dict[str, Any]:
    """
    Generate the full Claude Desktop MCP config snippet for ProjectMind.

    Returns:
        dict that should be merged into ``claude_desktop_config.json``
    """
    return {
        "mcpServers": {
            "projectmind": _build_mcp_entry()
        }
    }


def install_claude_desktop_config(dry_run: bool = False) -> None:
    """
    Add or update the ProjectMind MCP entry in Claude Desktop's config.

    Args:
        dry_run: If True, print the config change without writing to disk.
    """
    config_path = _get_claude_config_path()
    snippet = generate_claude_config_snippet()
    snippet_str = json.dumps(snippet, indent=2)

    if dry_run:
        _print_dry_run(config_path, snippet_str)
        return

    # Read existing config or start fresh
    if config_path.exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                existing_config: dict[str, Any] = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.error("Failed to read existing Claude config at %s: %s", config_path, e)
            _print_error(
                f"Could not read Claude Desktop config at:\n  {config_path}\n\nError: {e}\n\n"
                f"Please add the following to your Claude Desktop config manually:\n\n{snippet_str}"
            )
            return
    else:
        existing_config = {}

    # Merge mcpServers
    if "mcpServers" not in existing_config:
        existing_config["mcpServers"] = {}

    if "projectmind" in existing_config["mcpServers"]:
        action = "updated"
    else:
        action = "added"

    existing_config["mcpServers"]["projectmind"] = _build_mcp_entry()

    # Write back
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(existing_config, f, indent=2)
            f.write("\n")
        logger.info("Claude Desktop config %s at %s", action, config_path)
        _print_success(action, config_path)
    except OSError as e:
        logger.error("Failed to write Claude Desktop config: %s", e)
        _print_error(
            f"Could not write to:\n  {config_path}\n\nError: {e}\n\n"
            f"Please add the following manually:\n\n{snippet_str}"
        )


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def _print_dry_run(config_path: Path, snippet_str: str) -> None:
    if _RICH:
        console.print(
            Panel(
                f"[bold]Would update:[/bold] {config_path}\n\n"
                f"[bold]Snippet to merge:[/bold]\n\n"
                + snippet_str,
                title="[cyan]Dry Run — Claude Desktop Config[/cyan]",
                border_style="cyan",
            )
        )
    else:
        print(f"[DRY RUN] Would update: {config_path}")
        print(snippet_str)


def _print_success(action: str, config_path: Path) -> None:
    if _RICH:
        console.print(
            Panel(
                f"[bold green]✓[/bold green] ProjectMind MCP entry [cyan]{action}[/cyan] in Claude Desktop config.\n\n"
                f"  [dim]{config_path}[/dim]\n\n"
                f"[bold]Next steps:[/bold]\n"
                f"  1. Restart Claude Desktop\n"
                f"  2. Open a project in Claude\n"
                f"  3. Ask: [italic]\"What is this project about?\"[/italic]\n"
                f"     Claude will use [bold]get_project_summary[/bold] automatically.",
                title="[green]Claude Desktop Integration[/green]",
                border_style="green",
            )
        )
    else:
        print(f"✓ ProjectMind MCP {action} in Claude Desktop config: {config_path}")
        print("\nRestart Claude Desktop to activate.")


def _print_error(message: str) -> None:
    if _RICH:
        console.print(
            Panel(message, title="[red]Claude Desktop Setup Error[/red]", border_style="red")
        )
    else:
        print(f"Error: {message}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Adapter implementation
# ---------------------------------------------------------------------------


@register_adapter
class ClaudeDesktopAdapter(AgentAdapter):
    """
    Adapter that formats ProjectMind responses for Claude Desktop.

    Claude receives plain dict / list responses from MCP tools; this adapter
    provides a Markdown-formatted string view for when you want to embed
    context directly in a Claude conversation (rather than via MCP).
    """

    name = "Claude Desktop"
    identifier = "claude"

    def format_context(self, context: dict[str, Any]) -> str:
        """Format a project context as a Markdown string."""
        lines: list[str] = [
            f"# ProjectMind Context for Task\n",
            f"**Task:** {context.get('task', '')}\n",
            f"**Tokens:** {context.get('token_count', 0)} / {context.get('token_budget', 8000)}\n",
        ]

        # Warnings first — most critical
        if warnings := context.get("warnings", []):
            lines.append("\n## ⚠ Warnings\n")
            for w in warnings:
                lines.append(
                    f"- **[{w['severity'].upper()}]** {w['message']}"
                    + (f"\n  *Suggested action:* {w['suggested_action']}" if w.get("suggested_action") else "")
                )

        # Knowledge items
        if items := context.get("knowledge_items", []):
            lines.append("\n## Relevant Knowledge\n")
            for item in items:
                status = item.get("status", "current")
                status_marker = "🟡" if status == "stale" else ("🔴" if status == "contradicted" else "🟢")
                lines.append(f"### {status_marker} {item['title']} ({item['category']})\n")
                lines.append(f"{item['content']}\n")

        # Code chunks
        if chunks := context.get("code_chunks", []):
            lines.append("\n## Relevant Code\n")
            for chunk in chunks:
                lines.append(
                    f"**{chunk['file_path']}** (L{chunk['start_line']}–{chunk['end_line']})\n"
                    f"```{chunk.get('language', '')}\n{chunk['content']}\n```\n"
                )

        return "\n".join(lines)

    def format_knowledge(self, items: list[dict[str, Any]]) -> str:
        """Format knowledge items as Markdown."""
        if not items:
            return "_No relevant knowledge found._"
        lines = []
        for item in items:
            lines.append(f"**{item['title']}** ({item['category']}, {item['status']})")
            lines.append(item["content"])
            lines.append("")
        return "\n".join(lines)

    def format_warning(self, warnings: list[dict[str, Any]]) -> str:
        """Format warnings as Markdown."""
        if not warnings:
            return "_No warnings for this task._"
        lines = ["## ⚠ Warnings\n"]
        for w in warnings:
            lines.append(f"- **[{w['severity'].upper()}]** {w['message']}")
        return "\n".join(lines)
