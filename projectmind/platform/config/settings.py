"""
ProjectMind configuration system.

Settings are loaded from (in priority order):
1. Environment variables prefixed with ``PROJECTMIND_``
2. ``projectmind.toml`` in the project root
3. Built-in defaults

Example usage::

    from projectmind.platform.config.settings import get_settings
    settings = get_settings()
    print(settings.token_budget)
"""

from __future__ import annotations

import os
import tomllib  # type: ignore[assignment]
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Settings dataclasses (no external deps required)
# ---------------------------------------------------------------------------


class ProjectSettings:
    """Settings for the project being analysed."""

    def __init__(
        self,
        name: str = "my-project",
        root: str = ".",
        memory_dir: str = ".projectmind",
        exclude_patterns: list[str] | None = None,
    ):
        self.name = name
        self.root = Path(root).resolve()
        self.memory_dir = self.root / memory_dir
        self.exclude_patterns: list[str] = exclude_patterns or [
            "**/.env",
            "**/secrets/**",
            "**/__pycache__/**",
            "**/.git/**",
            "**/node_modules/**",
            "**/*.pyc",
        ]


class RetrievalSettings:
    """Settings for the context retrieval engine (Member 3)."""

    def __init__(
        self,
        token_budget: int = 8000,
        max_knowledge_items: int = 10,
        max_code_chunks: int = 5,
        min_relevance_score: float = 0.3,
    ):
        self.token_budget = token_budget
        self.max_knowledge_items = max_knowledge_items
        self.max_code_chunks = max_code_chunks
        self.min_relevance_score = min_relevance_score


class MCPSettings:
    """Settings for the MCP server."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 3333,
        transport: str = "stdio",  # "stdio" | "sse" | "http"
        enabled: bool = True,
    ):
        self.host = host
        self.port = port
        self.transport = transport
        self.enabled = enabled


class LoggingSettings:
    """Settings for the logging subsystem."""

    def __init__(
        self,
        level: str = "INFO",
        file: str | None = None,
        json_format: bool = False,
        max_bytes: int = 10 * 1024 * 1024,  # 10 MB
        backup_count: int = 3,
    ):
        self.level = level.upper()
        self.file = file
        self.json_format = json_format
        self.max_bytes = max_bytes
        self.backup_count = backup_count


class DatabaseSettings:
    """Settings for the SQLite database used by Member 2."""

    def __init__(self, path: str | None = None):
        # Default: <memory_dir>/projectmind.db — resolved later
        self.path = path


class Settings:
    """
    Top-level settings object for ProjectMind.

    Attributes are grouped by subsystem.
    """

    def __init__(
        self,
        project: ProjectSettings | None = None,
        retrieval: RetrievalSettings | None = None,
        mcp: MCPSettings | None = None,
        logging: LoggingSettings | None = None,
        database: DatabaseSettings | None = None,
    ):
        self.project = project or ProjectSettings()
        self.retrieval = retrieval or RetrievalSettings()
        self.mcp = mcp or MCPSettings()
        self.logging = logging or LoggingSettings()
        self.database = database or DatabaseSettings()

        # Resolve database path relative to memory_dir if not set
        if self.database.path is None:
            self.database.path = str(self.project.memory_dir / "projectmind.db")

        # Resolve log file path relative to memory_dir if not absolute
        if self.logging.file is None:
            self.logging.file = str(self.project.memory_dir / "logs" / "projectmind.log")

    @property
    def memory_dir(self) -> Path:
        return self.project.memory_dir

    @property
    def token_budget(self) -> int:
        return self.retrieval.token_budget


# ---------------------------------------------------------------------------
# TOML loader
# ---------------------------------------------------------------------------


def _load_toml(path: Path) -> dict[str, Any]:
    """Load a TOML file; return empty dict if unavailable."""
    if tomllib is None:
        return {}
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def _from_dict(data: dict[str, Any]) -> Settings:
    """Build a Settings object from a parsed TOML dict."""
    proj_data = data.get("project", {})
    retr_data = data.get("retrieval", {})
    mcp_data = data.get("mcp", {})
    log_data = data.get("logging", {})
    db_data = data.get("database", {})

    project = ProjectSettings(
        name=proj_data.get("name", "my-project"),
        root=proj_data.get("root", "."),
        memory_dir=proj_data.get("memory_dir", ".projectmind"),
        exclude_patterns=proj_data.get("exclude_patterns", None),
    )
    retrieval = RetrievalSettings(
        token_budget=retr_data.get("token_budget", 8000),
        max_knowledge_items=retr_data.get("max_knowledge_items", 10),
        max_code_chunks=retr_data.get("max_code_chunks", 5),
        min_relevance_score=retr_data.get("min_relevance_score", 0.3),
    )
    mcp = MCPSettings(
        host=mcp_data.get("host", "localhost"),
        port=mcp_data.get("port", 3333),
        transport=mcp_data.get("transport", "stdio"),
        enabled=mcp_data.get("enabled", True),
    )
    logging_s = LoggingSettings(
        level=log_data.get("level", "INFO"),
        file=log_data.get("file", None),
        json_format=log_data.get("json_format", False),
        max_bytes=log_data.get("max_bytes", 10 * 1024 * 1024),
        backup_count=log_data.get("backup_count", 3),
    )
    database = DatabaseSettings(
        path=db_data.get("path", None),
    )

    return Settings(
        project=project,
        retrieval=retrieval,
        mcp=mcp,
        logging=logging_s,
        database=database,
    )


# ---------------------------------------------------------------------------
# Environment variable overrides
# ---------------------------------------------------------------------------


def _apply_env_overrides(settings: Settings) -> None:
    """Apply PROJECTMIND_* environment variables over loaded settings."""
    env = os.environ

    # Project
    if v := env.get("PROJECTMIND_PROJECT_NAME"):
        settings.project.name = v
    if v := env.get("PROJECTMIND_PROJECT_ROOT"):
        settings.project.root = Path(v).resolve()
    if v := env.get("PROJECTMIND_MEMORY_DIR"):
        settings.project.memory_dir = Path(v)

    # Retrieval
    if v := env.get("PROJECTMIND_TOKEN_BUDGET"):
        settings.retrieval.token_budget = int(v)

    # MCP
    if v := env.get("PROJECTMIND_MCP_HOST"):
        settings.mcp.host = v
    if v := env.get("PROJECTMIND_MCP_PORT"):
        settings.mcp.port = int(v)
    if v := env.get("PROJECTMIND_MCP_TRANSPORT"):
        settings.mcp.transport = v

    # Logging
    if v := env.get("PROJECTMIND_LOG_LEVEL"):
        settings.logging.level = v.upper()
    if v := env.get("PROJECTMIND_LOG_FILE"):
        settings.logging.file = v

    # Database
    if v := env.get("PROJECTMIND_DB_PATH"):
        settings.database.path = v


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_CONFIG_FILENAME = "projectmind.toml"
_settings_cache: Settings | None = None


def load_settings(config_path: Path | str | None = None) -> Settings:
    """
    Load settings from a TOML file and environment variables.

    Args:
        config_path: Explicit path to ``projectmind.toml``. If None,
                     searches the current directory and its parents.
    """
    global _settings_cache

    if config_path is not None:
        toml_path: Path | None = Path(config_path)
    else:
        # Walk up from cwd looking for projectmind.toml
        toml_path = _find_config_file()

    data = _load_toml(toml_path) if toml_path else {}
    settings = _from_dict(data)
    _apply_env_overrides(settings)
    _settings_cache = settings
    return settings


def get_settings() -> Settings:
    """
    Return the cached settings (loads from disk if not yet loaded).
    Call ``load_settings()`` first for explicit control.
    """
    global _settings_cache
    if _settings_cache is None:
        _settings_cache = load_settings()
    return _settings_cache


def reset_settings() -> None:
    """Clear the settings cache (useful for testing)."""
    global _settings_cache
    _settings_cache = None


def _find_config_file(start: Path | None = None) -> Path | None:
    """Walk up directory tree from ``start`` to find ``projectmind.toml``."""
    current = (start or Path.cwd()).resolve()
    for directory in [current, *current.parents]:
        candidate = directory / _CONFIG_FILENAME
        if candidate.exists():
            return candidate
    return None


# ---------------------------------------------------------------------------
# Default config file template
# ---------------------------------------------------------------------------

DEFAULT_CONFIG_TEMPLATE = """\
# ProjectMind configuration file
# Documentation: https://github.com/Anushree-007/projectmind

[project]
name = "{project_name}"
root = "."
memory_dir = ".projectmind"
exclude_patterns = [
    "**/.env",
    "**/secrets/**",
    "**/__pycache__/**",
    "**/.git/**",
    "**/node_modules/**",
    "**/*.pyc",
]

[retrieval]
# Maximum tokens to include in a context response
token_budget = 8000
# Maximum knowledge items to retrieve per query
max_knowledge_items = 10
# Maximum code chunks to retrieve per query
max_code_chunks = 5
# Minimum relevance score (0.0–1.0) for retrieved items
min_relevance_score = 0.3

[mcp]
# MCP server transport: "stdio" (for Claude Desktop) or "sse" / "http"
transport = "stdio"
host = "localhost"
port = 3333
enabled = true

[logging]
level = "INFO"   # DEBUG | INFO | WARNING | ERROR
json_format = false

[database]
# SQLite database path (defaults to <memory_dir>/projectmind.db)
# path = ".projectmind/projectmind.db"
"""
