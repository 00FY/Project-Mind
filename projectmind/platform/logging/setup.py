"""
Logging and error handling for ProjectMind.

Provides:
- Structured, coloured console logging via ``rich``
- Rotating file logging (JSON or plain text)
- ``ProjectMindError`` base exception hierarchy
- Global exception hook that converts cryptic tracebacks into
  human-readable messages with actionable suggestions
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
import traceback
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from projectmind.platform.config.settings import LoggingSettings

# ---------------------------------------------------------------------------
# Exception hierarchy
# ---------------------------------------------------------------------------


class ProjectMindError(Exception):
    """
    Base exception for all ProjectMind errors.

    Attributes:
        message: Human-readable error description.
        suggestion: Actionable advice for the user.
        code: Short machine-readable error code (e.g. "DB_NOT_FOUND").
    """

    def __init__(
        self,
        message: str,
        suggestion: str = "",
        code: str = "PROJECTMIND_ERROR",
    ):
        super().__init__(message)
        self.message = message
        self.suggestion = suggestion
        self.code = code

    def __str__(self) -> str:  # noqa: D105
        parts = [f"[{self.code}] {self.message}"]
        if self.suggestion:
            parts.append(f"\nSuggestion: {self.suggestion}")
        return "\n".join(parts)


class ConfigurationError(ProjectMindError):
    """Raised when ``projectmind.toml`` is missing or invalid."""

    def __init__(self, message: str, suggestion: str = ""):
        super().__init__(
            message,
            suggestion or "Run 'projectmind init' to create a default config.",
            code="CONFIG_ERROR",
        )


class DatabaseError(ProjectMindError):
    """Raised when the SQLite database cannot be opened or queried."""

    def __init__(self, message: str, suggestion: str = ""):
        super().__init__(
            message,
            suggestion or "Run 'projectmind doctor' to diagnose database issues.",
            code="DB_ERROR",
        )


class IndexError(ProjectMindError):  # noqa: A001
    """Raised when the code index is missing or corrupted."""

    def __init__(self, message: str, suggestion: str = ""):
        super().__init__(
            message,
            suggestion or "Run 'projectmind index' to rebuild the index.",
            code="INDEX_ERROR",
        )


class MCPError(ProjectMindError):
    """Raised when the MCP server encounters an error."""

    def __init__(self, message: str, suggestion: str = ""):
        super().__init__(
            message,
            suggestion or "Run 'projectmind serve' to restart the MCP server.",
            code="MCP_ERROR",
        )


class ModuleNotReadyError(ProjectMindError):
    """Raised when a Member 1/2/3 module is not registered."""

    def __init__(self, member: str):
        super().__init__(
            f"{member} module is not available.",
            "Ensure all ProjectMind members have been installed and configured.",
            code="MODULE_NOT_READY",
        )


# ---------------------------------------------------------------------------
# Rich-based formatter (falls back gracefully if rich is not installed)
# ---------------------------------------------------------------------------


try:
    from rich.console import Console
    from rich.logging import RichHandler
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


class _JsonFormatter(logging.Formatter):
    """Emit log records as newline-delimited JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


# ---------------------------------------------------------------------------
# Setup function
# ---------------------------------------------------------------------------

_configured = False


def setup_logging(settings: LoggingSettings | None = None) -> None:
    """
    Configure the root ``projectmind`` logger.

    Call once at startup.  Safe to call multiple times (idempotent).

    Args:
        settings: Logging settings. Loads from config if None.
    """
    global _configured
    if _configured:
        return
    _configured = True

    if settings is None:
        from projectmind.platform.config.settings import get_settings
        settings = get_settings().logging

    root_logger = logging.getLogger("projectmind")
    root_logger.setLevel(getattr(logging, settings.level, logging.INFO))
    root_logger.handlers.clear()

    # --- Console handler ---
    if _RICH_AVAILABLE:
        console_handler: logging.Handler = RichHandler(
            rich_tracebacks=True,
            show_path=False,
            markup=True,
        )
        console_handler.setFormatter(logging.Formatter("%(message)s"))
    else:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
    root_logger.addHandler(console_handler)

    # --- File handler (rotating) ---
    if settings.file:
        log_path = Path(settings.file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path,
            maxBytes=settings.max_bytes,
            backupCount=settings.backup_count,
            encoding="utf-8",
        )
        if settings.json_format:
            file_handler.setFormatter(_JsonFormatter())
        else:
            file_handler.setFormatter(
                logging.Formatter(
                    fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%Y-%m-%dT%H:%M:%S",
                )
            )
        root_logger.addHandler(file_handler)


def reset_logging() -> None:
    """Reset logging configuration (useful for testing)."""
    global _configured
    _configured = False
    root_logger = logging.getLogger("projectmind")
    root_logger.handlers.clear()


# ---------------------------------------------------------------------------
# User-friendly exception hook
# ---------------------------------------------------------------------------

_ERROR_MAP: dict[type, tuple[str, str]] = {
    FileNotFoundError: (
        "A required file could not be found.",
        "Run 'projectmind doctor' to check your installation.",
    ),
    PermissionError: (
        "ProjectMind does not have permission to access a required file.",
        "Check file permissions and try again.",
    ),
    ConnectionRefusedError: (
        "ProjectMind could not connect to the MCP server.",
        "Run 'projectmind serve' to start the server.",
    ),
}


def install_exception_hook() -> None:
    """
    Replace the default sys.excepthook with a ProjectMind-friendly handler.

    This translates cryptic Python tracebacks into readable messages with
    actionable suggestions, while still logging the full traceback to the
    log file.
    """
    logger = logging.getLogger("projectmind.error")

    def _hook(exc_type: type, exc_value: BaseException, exc_tb: object) -> None:  # noqa: ANN001
        # Always log full traceback to file
        logger.error(
            "Unhandled exception",
            exc_info=(exc_type, exc_value, exc_tb),
        )

        # Friendly console output
        if isinstance(exc_value, ProjectMindError):
            _print_friendly_error(str(exc_value))
        elif exc_type in _ERROR_MAP:
            message, suggestion = _ERROR_MAP[exc_type]
            _print_friendly_error(
                f"{message}\n\nDetails: {exc_value}\n\nSuggestion: {suggestion}"
            )
        else:
            # Fall back to normal traceback for unexpected errors
            sys.__excepthook__(exc_type, exc_value, exc_tb)

    sys.excepthook = _hook


def _print_friendly_error(message: str) -> None:
    """Print a user-friendly error to stderr."""
    if _RICH_AVAILABLE:
        from rich.console import Console
        from rich.panel import Panel
        console = Console(stderr=True)
        console.print(
            Panel(
                message,
                title="[bold red]ProjectMind Error[/bold red]",
                border_style="red",
            )
        )
    else:
        print("\n── ProjectMind Error ──", file=sys.stderr)
        print(message, file=sys.stderr)
        print("─" * 40, file=sys.stderr)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger namespaced under ``projectmind``.

    Args:
        name: Sub-name, e.g. ``"cli"`` → ``"projectmind.cli"``
    """
    if not name.startswith("projectmind"):
        name = f"projectmind.{name}"
    return logging.getLogger(name)
