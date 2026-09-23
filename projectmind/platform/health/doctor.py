"""
ProjectMind health check / doctor module.

Runs a suite of checks and reports PASS / WARN / FAIL with actionable
messages. Invoked by ``projectmind doctor`` and the ``get_project_status``
MCP tool.

Each check is a small function that returns a ``CheckResult``.
"""

from __future__ import annotations

import importlib
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from projectmind.core.interfaces import HealthStatus, get_core
from projectmind.platform.config.settings import get_settings
from projectmind.platform.logging.setup import get_logger

logger = get_logger("health.doctor")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class CheckResult:
    """Result of a single health check."""

    name: str
    status: HealthStatus
    message: str
    suggestion: str = ""
    detail: str = ""

    @property
    def icon(self) -> str:
        icons = {
            HealthStatus.PASS: "[OK]",
            HealthStatus.WARN: "[WARN]",
            HealthStatus.FAIL: "[FAIL]",
        }
        return icons.get(self.status, "?")

    @property
    def color(self) -> str:
        colors = {
            HealthStatus.PASS: "green",
            HealthStatus.WARN: "yellow",
            HealthStatus.FAIL: "red",
        }
        return colors.get(self.status, "white")


@dataclass
class DoctorReport:
    """Aggregated result of all health checks."""

    checks: list[CheckResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def passed(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == HealthStatus.PASS]

    @property
    def warnings(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == HealthStatus.WARN]

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status == HealthStatus.FAIL]

    @property
    def is_healthy(self) -> bool:
        return len(self.failures) == 0

    @property
    def overall_status(self) -> HealthStatus:
        if self.failures:
            return HealthStatus.FAIL
        if self.warnings:
            return HealthStatus.WARN
        return HealthStatus.PASS


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_project_directory() -> CheckResult:
    """Check that the project root directory exists and is readable."""
    try:
        settings = get_settings()
        root = settings.project.root

        if not root.exists():
            return CheckResult(
                name="Project directory",
                status=HealthStatus.FAIL,
                message=f"Project root does not exist: {root}",
                suggestion="Set the correct path in projectmind.toml under [project] root.",
            )
        if not root.is_dir():
            return CheckResult(
                name="Project directory",
                status=HealthStatus.FAIL,
                message=f"Project root is not a directory: {root}",
                suggestion="Set the correct path in projectmind.toml under [project] root.",
            )
        # Test readability
        list(root.iterdir())
        return CheckResult(
            name="Project directory",
            status=HealthStatus.PASS,
            message=f"Project root is accessible: {root}",
        )
    except PermissionError as e:
        return CheckResult(
            name="Project directory",
            status=HealthStatus.FAIL,
            message=f"Cannot read project directory: {e}",
            suggestion="Check directory permissions.",
        )
    except Exception as e:
        return CheckResult(
            name="Project directory",
            status=HealthStatus.FAIL,
            message=f"Unexpected error checking project directory: {e}",
        )


def check_memory_directory() -> CheckResult:
    """Check that .projectmind/ has been initialised."""
    try:
        settings = get_settings()
        mem_dir = settings.project.memory_dir

        if not mem_dir.exists():
            return CheckResult(
                name="Memory directory",
                status=HealthStatus.FAIL,
                message=f".projectmind/ directory not found at: {mem_dir}",
                suggestion="Run 'projectmind init' to initialise the project.",
            )
        return CheckResult(
            name="Memory directory",
            status=HealthStatus.PASS,
            message=f"Memory directory found: {mem_dir}",
        )
    except Exception as e:
        return CheckResult(
            name="Memory directory",
            status=HealthStatus.FAIL,
            message=f"Error checking memory directory: {e}",
        )


def check_config_file() -> CheckResult:
    """Check that projectmind.toml is present and parseable."""
    try:
        from projectmind.platform.config.settings import _find_config_file

        config_path = _find_config_file()

        if config_path is None:
            return CheckResult(
                name="Configuration file",
                status=HealthStatus.WARN,
                message="projectmind.toml not found — using defaults.",
                suggestion="Run 'projectmind init' to create a config file.",
            )

        # Try to parse it
        import tomllib

        with open(config_path, "rb") as f:
            tomllib.load(f)

        return CheckResult(
            name="Configuration file",
            status=HealthStatus.PASS,
            message=f"Config file valid: {config_path}",
        )
    except Exception as e:
        return CheckResult(
            name="Configuration file",
            status=HealthStatus.FAIL,
            message=f"Config file is invalid: {e}",
            suggestion="Fix the TOML syntax in projectmind.toml and try again.",
        )


def check_database() -> CheckResult:
    """Check that the SQLite database is accessible and not corrupted."""
    try:
        settings = get_settings()
        db_path = settings.database.path

        if db_path is None:
            return CheckResult(
                name="Database",
                status=HealthStatus.FAIL,
                message="Database path is not configured.",
                suggestion="Run 'projectmind init' to set up the database.",
            )

        db_file = Path(db_path)
        if not db_file.exists():
            return CheckResult(
                name="Database",
                status=HealthStatus.WARN,
                message=f"Database not yet created: {db_file}",
                suggestion="Run 'projectmind index' to build the index and create the database.",
            )

        # Try to open and run integrity check
        conn = sqlite3.connect(str(db_file), timeout=5.0)
        cursor = conn.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        conn.close()

        if result and result[0] == "ok":
            size_kb = db_file.stat().st_size // 1024
            return CheckResult(
                name="Database",
                status=HealthStatus.PASS,
                message=f"Database is healthy ({size_kb} KB): {db_file}",
            )
        else:
            return CheckResult(
                name="Database",
                status=HealthStatus.FAIL,
                message=f"Database integrity check failed: {result}",
                suggestion="Delete the database and run 'projectmind index' to rebuild.",
            )
    except sqlite3.DatabaseError as e:
        return CheckResult(
            name="Database",
            status=HealthStatus.FAIL,
            message=f"Database is corrupted or inaccessible: {e}",
            suggestion=(
                "Delete the database file and run 'projectmind index' to rebuild. "
                "Run 'projectmind doctor' for more details."
            ),
        )
    except Exception as e:
        return CheckResult(
            name="Database",
            status=HealthStatus.FAIL,
            message=f"Unexpected database error: {e}",
        )


def check_memory_integrity() -> CheckResult:
    """Check that Member 2 (ProjectMemory) is reachable and healthy."""
    try:
        core = get_core()
        if core._project_memory is None:
            return CheckResult(
                name="Memory integrity",
                status=HealthStatus.WARN,
                message="ProjectMemory (Member 2) module is not registered.",
                suggestion="Ensure Member 2 is installed and imported at startup.",
            )

        if core.project_memory.is_healthy():
            status = core.project_memory.get_status()
            return CheckResult(
                name="Memory integrity",
                status=HealthStatus.PASS,
                message=(
                    f"Memory is healthy — "
                    f"{status.current_items} current items, "
                    f"{status.stale_items} stale."
                ),
            )
        else:
            status = core.project_memory.get_status()
            return CheckResult(
                name="Memory integrity",
                status=HealthStatus.FAIL,
                message=f"Memory engine reports unhealthy: {status.error_message}",
                suggestion="Run 'projectmind doctor' for details.",
            )
    except Exception as e:
        return CheckResult(
            name="Memory integrity",
            status=HealthStatus.WARN,
            message=f"Could not check memory integrity: {e}",
            suggestion="Ensure Member 2 module is installed.",
        )


def check_index_freshness() -> CheckResult:
    """Check that Member 1 (CodeIntelligence) has a recent index."""
    try:
        core = get_core()
        if core._code_intelligence is None:
            return CheckResult(
                name="Index freshness",
                status=HealthStatus.WARN,
                message="CodeIntelligence (Member 1) module is not registered.",
                suggestion="Ensure Member 1 is installed and imported at startup.",
            )

        last_indexed = core.code_intelligence.get_last_indexed()
        if last_indexed is None:
            return CheckResult(
                name="Index freshness",
                status=HealthStatus.WARN,
                message="Project has not been indexed yet.",
                suggestion="Run 'projectmind index' to build the code index.",
            )

        age = datetime.utcnow() - last_indexed.replace(tzinfo=None)
        if age > timedelta(days=7):
            return CheckResult(
                name="Index freshness",
                status=HealthStatus.WARN,
                message=f"Index is {age.days} days old.",
                suggestion="Run 'projectmind index' to refresh.",
                detail=f"Last indexed: {last_indexed.isoformat()}",
            )
        return CheckResult(
            name="Index freshness",
            status=HealthStatus.PASS,
            message=f"Index is fresh (last indexed {age.seconds // 3600}h ago).",
            detail=f"Last indexed: {last_indexed.isoformat()}",
        )
    except Exception as e:
        return CheckResult(
            name="Index freshness",
            status=HealthStatus.WARN,
            message=f"Could not check index freshness: {e}",
        )


def check_mcp_configuration() -> CheckResult:
    """Check that the MCP server configuration is valid."""
    try:
        settings = get_settings()
        mcp = settings.mcp

        if not mcp.enabled:
            return CheckResult(
                name="MCP configuration",
                status=HealthStatus.WARN,
                message="MCP server is disabled in configuration.",
                suggestion="Set [mcp] enabled = true in projectmind.toml to enable.",
            )

        valid_transports = {"stdio", "sse", "http"}
        if mcp.transport not in valid_transports:
            return CheckResult(
                name="MCP configuration",
                status=HealthStatus.FAIL,
                message=f"Invalid MCP transport: '{mcp.transport}'",
                suggestion=f"Set [mcp] transport to one of: {', '.join(valid_transports)}",
            )

        return CheckResult(
            name="MCP configuration",
            status=HealthStatus.PASS,
            message=f"MCP configured: transport={mcp.transport}, port={mcp.port}",
        )
    except Exception as e:
        return CheckResult(
            name="MCP configuration",
            status=HealthStatus.FAIL,
            message=f"MCP configuration error: {e}",
        )


def check_claude_desktop() -> CheckResult:
    """Check if Claude Desktop MCP configuration is installed."""
    import platform as plat

    try:
        system = plat.system()
        if system == "Darwin":
            config_path = (
                Path.home()
                / "Library"
                / "Application Support"
                / "Claude"
                / "claude_desktop_config.json"
            )
        elif system == "Windows":
            appdata = Path(
                sys.platform == "win32" and __import__("os").environ.get("APPDATA", "") or ""
            )
            config_path = appdata / "Claude" / "claude_desktop_config.json"
        else:
            config_path = Path.home() / ".config" / "Claude" / "claude_desktop_config.json"

        if not config_path.exists():
            return CheckResult(
                name="Claude Desktop integration",
                status=HealthStatus.WARN,
                message="Claude Desktop config not found.",
                suggestion="Run 'projectmind connect claude' to configure Claude Desktop.",
            )

        import json

        with open(config_path) as f:
            config = json.load(f)

        servers = config.get("mcpServers", {})
        if "projectmind" not in servers:
            return CheckResult(
                name="Claude Desktop integration",
                status=HealthStatus.WARN,
                message="Claude Desktop is installed but ProjectMind MCP is not configured.",
                suggestion="Run 'projectmind connect claude' to add ProjectMind to Claude Desktop.",
            )

        return CheckResult(
            name="Claude Desktop integration",
            status=HealthStatus.PASS,
            message="ProjectMind is configured in Claude Desktop.",
            detail=str(config_path),
        )
    except Exception as e:
        return CheckResult(
            name="Claude Desktop integration",
            status=HealthStatus.WARN,
            message=f"Could not check Claude Desktop config: {e}",
        )


def check_required_packages() -> CheckResult:
    """Check that all required Python packages are installed."""
    required = {
        "click": "click",
        "rich": "rich",
        "fastmcp": "fastmcp",
    }
    optional = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
    }

    missing_required = []
    missing_optional = []

    for display_name, module_name in required.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing_required.append(display_name)

    for display_name, module_name in optional.items():
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing_optional.append(display_name)

    if missing_required:
        return CheckResult(
            name="Required packages",
            status=HealthStatus.FAIL,
            message=f"Missing required packages: {', '.join(missing_required)}",
            suggestion="Run 'pip install projectmind' to install all dependencies.",
        )

    if missing_optional:
        missing_str = " ".join(missing_optional)
        return CheckResult(
            name="Required packages",
            status=HealthStatus.WARN,
            message=f"Optional packages not installed: {', '.join(missing_optional)}",
            suggestion=f"Run 'pip install {missing_str}' for full functionality.",
        )

    return CheckResult(
        name="Required packages",
        status=HealthStatus.PASS,
        message="All required packages are installed.",
    )


# ---------------------------------------------------------------------------
# Doctor runner
# ---------------------------------------------------------------------------

# Ordered list of all checks
ALL_CHECKS = [
    check_required_packages,
    check_project_directory,
    check_config_file,
    check_memory_directory,
    check_database,
    check_memory_integrity,
    check_index_freshness,
    check_mcp_configuration,
    check_claude_desktop,
]


def run_doctor(checks: list | None = None) -> DoctorReport:
    """
    Run all health checks and return a DoctorReport.

    Args:
        checks: Optional list of check functions to run.
                Defaults to ALL_CHECKS.
    """
    report = DoctorReport()
    selected_checks = checks or ALL_CHECKS

    for check_fn in selected_checks:
        try:
            result = check_fn()
            report.checks.append(result)
            logger.debug("Health check '%s': %s", result.name, result.status.value)
        except Exception as e:
            # Never let a check crash the doctor command
            report.checks.append(
                CheckResult(
                    name=getattr(check_fn, "__name__", "unknown"),
                    status=HealthStatus.FAIL,
                    message=f"Check crashed unexpectedly: {e}",
                    suggestion="This is a bug in ProjectMind. Please file an issue.",
                )
            )

    return report
