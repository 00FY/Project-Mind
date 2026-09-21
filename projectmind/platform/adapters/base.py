"""
Abstract base class for ProjectMind agent adapters.

An adapter formats MCP tool responses for a specific agent's
expected schema or calling convention.

To add a new adapter:
1. Subclass ``AgentAdapter``
2. Override ``format_context``, ``format_knowledge``, ``format_warning``
3. Register it with the CLI ``connect`` command
"""

from __future__ import annotations

import abc
from typing import Any


class AgentAdapter(abc.ABC):
    """
    Abstract base for agent-specific response formatters.

    The MCP server returns rich Python dicts.  An adapter takes those dicts
    and transforms them into whatever format a specific agent expects
    (e.g. a specific XML schema, a Markdown string, an OpenAI tool result, etc.)
    """

    #: Human-readable name of this adapter (e.g. "Claude Desktop")
    name: str = "BaseAdapter"

    #: Short identifier used in CLI (e.g. "claude", "ollama")
    identifier: str = "base"

    @abc.abstractmethod
    def format_context(self, context: dict[str, Any]) -> Any:
        """
        Format a ``get_project_context`` response for the target agent.

        Args:
            context: The dict returned by the ``get_project_context`` MCP tool.

        Returns:
            Agent-specific representation of the context.
        """
        ...

    @abc.abstractmethod
    def format_knowledge(self, items: list[dict[str, Any]]) -> Any:
        """
        Format a list of knowledge items for the target agent.

        Args:
            items: The list returned by ``search_project_knowledge``.
        """
        ...

    @abc.abstractmethod
    def format_warning(self, warnings: list[dict[str, Any]]) -> Any:
        """
        Format a list of warnings for the target agent.

        Args:
            warnings: The list returned by ``get_project_warnings``.
        """
        ...

    def format_summary(self, summary: dict[str, Any]) -> Any:  # noqa: D102
        """
        Format a project summary.  Default: pass-through.

        Args:
            summary: The dict returned by ``get_project_summary``.
        """
        return summary


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

_registry: dict[str, type[AgentAdapter]] = {}


def register_adapter(adapter_cls: type[AgentAdapter]) -> type[AgentAdapter]:
    """Decorator to register an adapter in the global registry."""
    _registry[adapter_cls.identifier] = adapter_cls
    return adapter_cls


def get_adapter(identifier: str) -> AgentAdapter:
    """
    Retrieve an adapter instance by identifier.

    Args:
        identifier: Short name, e.g. ``"claude"``, ``"ollama"``.

    Raises:
        KeyError: If no adapter with that identifier is registered.
    """
    if identifier not in _registry:
        available = ", ".join(_registry.keys()) or "none"
        raise KeyError(f"Unknown adapter '{identifier}'. Available adapters: {available}")
    return _registry[identifier]()


def list_adapters() -> list[str]:
    """Return all registered adapter identifiers."""
    return list(_registry.keys())
