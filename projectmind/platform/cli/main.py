"""
ProjectMind CLI — projectmind

Commands
--------
  init      Initialise a project (creates .projectmind/ and projectmind.toml)
  index     Index the codebase via Member 1
  status    Show memory and index stats
  query     Search project knowledge
  context   Get task-aware context for an AI agent
  audit     Audit project memory for stale / contradicted items
  doctor    Run health checks
  serve     Start the MCP server
  connect   Connect ProjectMind to an AI agent (e.g. Claude Desktop)

Usage::

    projectmind init
    projectmind doctor
    projectmind serve
    projectmind query "Why did we choose PostgreSQL?"
    projectmind context "I want to remove the auth middleware"
    projectmind connect claude
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click

# Lazy import so CLI starts fast even if optional deps are missing
try:
    from rich import print as rprint
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    _RICH = True
    console = Console()
    err_console = Console(stderr=True)
except ImportError:
    _RICH = False
    console = None  # type: ignore[assignment]
    err_console = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print(msg: str, style: str = "") -> None:
    if _RICH:
        console.print(msg, style=style)
    else:
        print(msg)


def _print_err(msg: str, style: str = "red") -> None:
    if _RICH:
        err_console.print(f"[{style}]{msg}[/{style}]")
    else:
        print(msg, file=sys.stderr)


def _ensure_init() -> None:
    """Exit with a friendly error if project is not initialised."""
    from projectmind.platform.config.settings import get_settings
    settings = get_settings()
    if not settings.project.memory_dir.exists():
        _print_err(
            "ProjectMind is not initialised in this directory.\n"
            "Run:  projectmind init"
        )
        sys.exit(1)


def _bootstrap() -> None:
    """Set up logging and exception hook once for every command."""
    from projectmind.platform.logging.setup import install_exception_hook, setup_logging
    setup_logging()
    install_exception_hook()


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(package_name="projectmind", prog_name="projectmind")
def cli() -> None:
    """
    ProjectMind — local project intelligence for AI coding agents.

    Run 'projectmind COMMAND --help' for help on a specific command.
    """
    _bootstrap()


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--name", "-n",
    default=None,
    help="Project name (defaults to current directory name).",
)
@click.option(
    "--force", "-f",
    is_flag=True,
    default=False,
    help="Overwrite existing configuration.",
)
def init(name: str | None, force: bool) -> None:
    """Initialise ProjectMind in the current directory.

    Creates:
      .projectmind/          Memory and index storage
      projectmind.toml       Configuration file
    """
    from projectmind.platform.config.settings import DEFAULT_CONFIG_TEMPLATE

    cwd = Path.cwd()
    project_name = name or cwd.name
    config_path = cwd / "projectmind.toml"
    mem_dir = cwd / ".projectmind"
    logs_dir = mem_dir / "logs"

    # Check existing
    if config_path.exists() and not force:
        _print_err(
            "projectmind.toml already exists.\n"
            "Use --force to overwrite."
        )
        sys.exit(1)

    # Create directories
    mem_dir.mkdir(exist_ok=True)
    logs_dir.mkdir(exist_ok=True)
    (mem_dir / ".gitignore").write_text(
        "# ProjectMind internal files — do not commit\n*\n!.gitignore\n"
    )

    # Write config
    config_content = DEFAULT_CONFIG_TEMPLATE.format(project_name=project_name)
    config_path.write_text(config_content, encoding="utf-8")

    if _RICH:
        console.print(
            Panel(
                f"[bold green]✓[/bold green] ProjectMind initialised for project: [cyan]{project_name}[/cyan]\n\n"
                f"  • Config:       [dim]{config_path}[/dim]\n"
                f"  • Memory dir:   [dim]{mem_dir}[/dim]\n\n"
                f"Next steps:\n"
                f"  [bold]projectmind index[/bold]   — index your codebase\n"
                f"  [bold]projectmind doctor[/bold]  — verify your installation\n"
                f"  [bold]projectmind serve[/bold]   — start the MCP server",
                title="ProjectMind Init",
                border_style="green",
            )
        )
    else:
        print(f"✓ Initialised project: {project_name}")
        print(f"  Config: {config_path}")
        print(f"  Memory: {mem_dir}")
        print("\nRun: projectmind index")


# ---------------------------------------------------------------------------
# index
# ---------------------------------------------------------------------------


@cli.command()
@click.option(
    "--path", "-p",
    default=None,
    help="Project root to index (defaults to configured project.root).",
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    default=False,
    help="Show detailed indexing progress.",
)
def index(path: str | None, verbose: bool) -> None:
    """Index the project codebase.

    Calls Member 1 (CodeIntelligence) to parse all source files and build
    the code index. Run this after initialisation and after major code changes.
    """
    _ensure_init()
    from projectmind.core.interfaces import get_core
    from projectmind.platform.config.settings import get_settings

    settings = get_settings()
    project_root = str(Path(path).resolve() if path else settings.project.root)

    _print(f"[bold]Indexing project:[/bold] {project_root}" if _RICH else f"Indexing: {project_root}")

    try:
        core = get_core()
        result = core.code_intelligence.index_project(project_root)

        if _RICH:
            table = Table(title="Index Results", border_style="blue")
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="green")
            table.add_row("Files indexed", str(result.files_indexed))
            table.add_row("Files skipped", str(result.files_skipped))
            table.add_row("Duration", f"{result.duration_seconds:.2f}s")
            if result.errors:
                table.add_row("Errors", str(len(result.errors)))
            console.print(table)
            if verbose and result.errors:
                for err in result.errors:
                    console.print(f"  [red]✗[/red] {err}")
        else:
            print(f"✓ Indexed {result.files_indexed} files in {result.duration_seconds:.2f}s")
            if result.errors:
                print(f"  ⚠ {len(result.errors)} errors")

    except RuntimeError as e:
        _print_err(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@cli.command()
def status() -> None:
    """Show project memory and index status."""
    _ensure_init()
    from projectmind.core.interfaces import get_core

    try:
        core = get_core()

        if _RICH:
            table = Table(title="ProjectMind Status", border_style="blue")
            table.add_column("Component", style="cyan", width=24)
            table.add_column("Status", style="green", width=16)
            table.add_column("Details")

            # Memory status
            if core._project_memory is not None:
                mem = core.project_memory.get_status()
                status_icon = "✓" if mem.is_healthy else "✗"
                status_color = "green" if mem.is_healthy else "red"
                table.add_row(
                    "Project Memory",
                    f"[{status_color}]{status_icon} {'healthy' if mem.is_healthy else 'error'}[/{status_color}]",
                    f"{mem.current_items} current, {mem.stale_items} stale",
                )
            else:
                table.add_row("Project Memory", "[yellow]⚠ not registered[/yellow]", "")

            # Index status
            if core._code_intelligence is not None:
                last = core.code_intelligence.get_last_indexed()
                if last:
                    table.add_row(
                        "Code Index",
                        "[green]✓ indexed[/green]",
                        f"Last: {last.strftime('%Y-%m-%d %H:%M')}",
                    )
                else:
                    table.add_row("Code Index", "[yellow]⚠ not indexed[/yellow]", "Run 'projectmind index'")
            else:
                table.add_row("Code Index", "[yellow]⚠ not registered[/yellow]", "")

            console.print(table)
        else:
            print("ProjectMind Status")
            print("-" * 40)
            modules = core.available_modules()
            for name, available in modules.items():
                icon = "✓" if available else "⚠"
                print(f"  {icon} {name}: {'available' if available else 'not registered'}")

    except Exception as e:
        _print_err(f"Could not get status: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("query_text")
@click.option("--limit", "-l", default=5, help="Maximum results to return.", show_default=True)
@click.option(
    "--category", "-c",
    default=None,
    multiple=True,
    help="Filter by category (goal, decision, constraint, architecture, history).",
)
@click.option("--json-output", is_flag=True, default=False, help="Output results as JSON.")
def query(query_text: str, limit: int, category: tuple[str, ...], json_output: bool) -> None:
    """Search project knowledge.

    Example:
        projectmind query "Why did we choose PostgreSQL?"
        projectmind query "authentication" --category constraint
    """
    _ensure_init()
    from projectmind.core.interfaces import get_core

    try:
        core = get_core()
        categories = list(category) if category else None
        results = core.project_memory.search_knowledge(
            query=query_text,
            limit=limit,
            categories=categories,
        )

        if json_output:
            output = [
                {
                    "id": r.id,
                    "category": r.category,
                    "title": r.title,
                    "content": r.content,
                    "status": r.status.value,
                    "relevance": r.relevance_score,
                }
                for r in results
            ]
            click.echo(json.dumps(output, indent=2, default=str))
            return

        if not results:
            _print("[yellow]No results found.[/yellow]" if _RICH else "No results found.")
            return

        if _RICH:
            for i, item in enumerate(results, 1):
                status_colors = {
                    "current": "green",
                    "stale": "yellow",
                    "contradicted": "red",
                    "historical": "dim",
                }
                color = status_colors.get(item.status.value, "white")
                console.print(
                    Panel(
                        f"{item.content}\n\n"
                        f"[dim]Category:[/dim] {item.category}  "
                        f"[dim]Status:[/dim] [{color}]{item.status.value}[/{color}]  "
                        f"[dim]Relevance:[/dim] {item.relevance_score:.2f}",
                        title=f"[bold]{i}. {item.title}[/bold]",
                        border_style=color,
                    )
                )
        else:
            for i, item in enumerate(results, 1):
                print(f"\n{i}. {item.title} [{item.status.value}]")
                print(f"   {item.content}")

    except RuntimeError as e:
        _print_err(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------


@cli.command()
@click.argument("task_description")
@click.option(
    "--budget", "-b",
    default=None,
    type=int,
    help="Token budget (overrides config).",
)
@click.option("--no-code", is_flag=True, default=False, help="Exclude code chunks.")
@click.option("--json-output", is_flag=True, default=False, help="Output as JSON.")
def context(task_description: str, budget: int | None, no_code: bool, json_output: bool) -> None:
    """Get task-aware context for an AI agent.

    Calls Member 3 (ContextRetriever) to assemble the minimum-sufficient
    context for the given task within the configured token budget.

    Example:
        projectmind context "I want to remove the auth middleware"
        projectmind context "Add a new user endpoint" --budget 4000
    """
    _ensure_init()
    from projectmind.core.interfaces import get_core
    from projectmind.platform.config.settings import get_settings

    settings = get_settings()
    token_budget = budget or settings.token_budget

    try:
        core = get_core()
        ctx = core.context_retriever.get_context(
            task=task_description,
            token_budget=token_budget,
            include_code=not no_code,
        )

        if json_output:
            output = {
                "task": ctx.task,
                "token_count": ctx.token_count,
                "token_budget": ctx.token_budget,
                "knowledge_items": [
                    {"title": k.title, "content": k.content, "status": k.status.value}
                    for k in ctx.knowledge_items
                ],
                "code_chunks": [
                    {"file": c.file_path, "lines": f"{c.start_line}-{c.end_line}", "content": c.content}
                    for c in ctx.code_chunks
                ],
                "warnings": [
                    {"severity": w.severity, "message": w.message}
                    for w in ctx.warnings
                ],
            }
            click.echo(json.dumps(output, indent=2, default=str))
            return

        if _RICH:
            console.print(
                Panel(
                    f"[bold]Task:[/bold] {ctx.task}\n"
                    f"[bold]Tokens:[/bold] {ctx.token_count} / {ctx.token_budget}\n"
                    f"[bold]Knowledge items:[/bold] {len(ctx.knowledge_items)}\n"
                    f"[bold]Code chunks:[/bold] {len(ctx.code_chunks)}\n"
                    f"[bold]Warnings:[/bold] {len(ctx.warnings)}",
                    title="Context Summary",
                    border_style="blue",
                )
            )

            if ctx.warnings:
                console.print("\n[bold red]⚠ Warnings[/bold red]")
                for w in ctx.warnings:
                    sev_colors = {"critical": "red", "high": "red", "medium": "yellow", "low": "cyan"}
                    color = sev_colors.get(w.severity, "white")
                    console.print(f"  [{color}][{w.severity.upper()}][/{color}] {w.message}")

            if ctx.knowledge_items:
                console.print("\n[bold]Relevant Knowledge[/bold]")
                for item in ctx.knowledge_items:
                    console.print(f"  • [cyan]{item.title}[/cyan]: {item.content[:120]}...")

            if ctx.code_chunks and not no_code:
                console.print("\n[bold]Relevant Code[/bold]")
                for chunk in ctx.code_chunks:
                    console.print(
                        f"  • [cyan]{chunk.file_path}[/cyan] "
                        f"L{chunk.start_line}-{chunk.end_line}"
                    )
        else:
            print(f"Task: {ctx.task}")
            print(f"Tokens: {ctx.token_count}/{ctx.token_budget}")
            print(f"Knowledge: {len(ctx.knowledge_items)} items")
            print(f"Code: {len(ctx.code_chunks)} chunks")
            print(f"Warnings: {len(ctx.warnings)}")

    except RuntimeError as e:
        _print_err(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# audit
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--json-output", is_flag=True, default=False, help="Output as JSON.")
def audit(json_output: bool) -> None:
    """Audit project memory for stale or contradicted knowledge.

    Calls Member 2 to identify items that may no longer be valid.
    """
    _ensure_init()
    from projectmind.core.interfaces import get_core

    try:
        core = get_core()
        report = core.project_memory.audit_memory()

        if json_output:
            output = {
                "stale_items": [{"id": i.id, "title": i.title} for i in report.stale_items],
                "contradicted_items": [{"id": i.id, "title": i.title} for i in report.contradicted_items],
                "missing_evidence": [{"id": i.id, "title": i.title} for i in report.missing_evidence],
                "recommendations": report.recommendations,
                "timestamp": report.timestamp.isoformat(),
            }
            click.echo(json.dumps(output, indent=2))
            return

        if _RICH:
            table = Table(title="Memory Audit Report", border_style="yellow")
            table.add_column("Issue", style="yellow")
            table.add_column("Count", justify="right")

            table.add_row("Stale items", str(len(report.stale_items)))
            table.add_row("Contradicted items", str(len(report.contradicted_items)))
            table.add_row("Missing evidence", str(len(report.missing_evidence)))
            console.print(table)

            if report.recommendations:
                console.print("\n[bold]Recommendations[/bold]")
                for rec in report.recommendations:
                    console.print(f"  → {rec}")
        else:
            print("Audit Report")
            print(f"  Stale: {len(report.stale_items)}")
            print(f"  Contradicted: {len(report.contradicted_items)}")
            print(f"  Recommendations: {len(report.recommendations)}")

    except RuntimeError as e:
        _print_err(str(e))
        sys.exit(1)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--json-output", is_flag=True, default=False, help="Output as JSON.")
def doctor(json_output: bool) -> None:
    """Run health checks on your ProjectMind installation.

    Checks project directory, config, database, memory integrity,
    index freshness, MCP configuration, and Claude Desktop integration.
    """
    from projectmind.core.interfaces import HealthStatus
    from projectmind.platform.health.doctor import run_doctor

    if not json_output:
        _print("[bold]Running ProjectMind health checks...[/bold]\n" if _RICH else "Running health checks...")

    report = run_doctor()

    if json_output:
        output = {
            "overall": report.overall_status.value,
            "is_healthy": report.is_healthy,
            "timestamp": report.timestamp.isoformat(),
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "message": c.message,
                    "suggestion": c.suggestion,
                    "detail": c.detail,
                }
                for c in report.checks
            ],
        }
        click.echo(json.dumps(output, indent=2))
        return

    if _RICH:
        table = Table(border_style="blue", show_header=True)
        table.add_column("", width=2)
        table.add_column("Check", style="bold", width=28)
        table.add_column("Message")
        table.add_column("Suggestion", style="dim")

        for check in report.checks:
            color_map = {
                HealthStatus.PASS: "green",
                HealthStatus.WARN: "yellow",
                HealthStatus.FAIL: "red",
            }
            color = color_map.get(check.status, "white")
            table.add_row(
                f"[{color}]{check.icon}[/{color}]",
                check.name,
                check.message,
                check.suggestion,
            )

        console.print(table)

        # Summary
        overall_color = {
            HealthStatus.PASS: "green",
            HealthStatus.WARN: "yellow",
            HealthStatus.FAIL: "red",
        }.get(report.overall_status, "white")

        console.print(
            f"\n[{overall_color}]Overall: {report.overall_status.value.upper()}[/{overall_color}]  "
            f"[green]{len(report.passed)} passed[/green]  "
            f"[yellow]{len(report.warnings)} warnings[/yellow]  "
            f"[red]{len(report.failures)} failures[/red]"
        )
    else:
        for check in report.checks:
            print(f"  {check.icon} {check.name}: {check.message}")
            if check.suggestion:
                print(f"      → {check.suggestion}")
        print(f"\nOverall: {report.overall_status.value.upper()}")

    if not report.is_healthy:
        sys.exit(1)


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------


@cli.command()
@click.option("--transport", "-t", default=None, help="Transport: stdio | sse | http")
@click.option("--port", "-p", default=None, type=int, help="Port (for sse/http transport).")
def serve(transport: str | None, port: int | None) -> None:
    """Start the ProjectMind MCP server.

    For use with Claude Desktop and other MCP-compatible agents, use
    the default 'stdio' transport:

        projectmind serve

    For HTTP/SSE (e.g. testing with curl):

        projectmind serve --transport sse --port 3333
    """
    _ensure_init()
    from projectmind.platform.config.settings import get_settings
    from projectmind.platform.mcp.server import create_server

    settings = get_settings()
    selected_transport = transport or settings.mcp.transport
    selected_port = port or settings.mcp.port

    _print(
        f"[bold green]Starting ProjectMind MCP server[/bold green] "
        f"(transport=[cyan]{selected_transport}[/cyan], port=[cyan]{selected_port}[/cyan])"
        if _RICH
        else f"Starting MCP server (transport={selected_transport}, port={selected_port})"
    )

    try:
        mcp_server = create_server()
        if selected_transport == "stdio":
            mcp_server.run()
        elif selected_transport in ("sse", "http"):
            mcp_server.run(transport=selected_transport, host=settings.mcp.host, port=selected_port)
        else:
            _print_err(f"Unknown transport: {selected_transport}. Use stdio, sse, or http.")
            sys.exit(1)
    except KeyboardInterrupt:
        _print("\n[yellow]MCP server stopped.[/yellow]" if _RICH else "\nMCP server stopped.")
    except Exception as e:
        _print_err(f"MCP server error: {e}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# connect
# ---------------------------------------------------------------------------


@cli.group()
def connect() -> None:
    """Connect ProjectMind to an AI agent or tool."""


@connect.command(name="claude")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the config that would be written without modifying files.",
)
def connect_claude(dry_run: bool) -> None:
    """Configure Claude Desktop to use ProjectMind as an MCP server.

    Finds the Claude Desktop config file and adds (or updates) the
    ProjectMind MCP server entry.

    Example:
        projectmind connect claude
        projectmind connect claude --dry-run
    """
    from projectmind.platform.adapters.claude_desktop import install_claude_desktop_config

    install_claude_desktop_config(dry_run=dry_run)


@connect.command(name="ollama")
@click.option("--host", default="http://localhost:11434", help="Ollama server URL.")
@click.option("--model", default="llama3", help="Default model to use.", show_default=True)
def connect_ollama(host: str, model: str) -> None:
    """Configure a local Ollama agent to use ProjectMind.

    Prints example code for calling ProjectMind context tools
    from an Ollama-based agent.
    """
    from projectmind.platform.adapters.ollama import print_ollama_integration_guide
    print_ollama_integration_guide(host=host, model=model)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the ``projectmind`` CLI."""
    cli()


if __name__ == "__main__":
    main()
