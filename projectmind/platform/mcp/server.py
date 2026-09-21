"""
ProjectMind MCP Server (Member 4)

Exposes ProjectMind's capabilities to AI agents (Claude Desktop, etc.)
through the Model Context Protocol using the FastMCP library.

Tools exposed
-------------
  get_project_summary       High-level project overview from memory
  search_project_knowledge  Semantic search over project knowledge
  get_relevant_code         Code chunks relevant to a query
  get_project_context       Full task-aware context (token-budgeted)
  get_project_status        Index and memory freshness report
  audit_project             Identify stale / contradicted knowledge
  get_project_warnings      Constraint / risk warnings for a task

Design principle
----------------
This file contains ONLY the MCP interface layer.
All intelligence lives in Members 1, 2, and 3.
Each tool delegates immediately to the core interfaces defined in
``projectmind.core.interfaces``.

Usage::

    # Start via CLI (recommended):
    projectmind serve

    # Or import directly:
    from projectmind.platform.mcp.server import create_server
    mcp = create_server()
    mcp.run()
"""

from __future__ import annotations

from typing import Any

import fastmcp

from projectmind.core.interfaces import (
    AuditReport,
    CodeChunk,
    KnowledgeItem,
    ProjectContext,
    ProjectSummary,
    Warning,
    get_core,
)
from projectmind.platform.config.settings import get_settings
from projectmind.platform.logging.setup import get_logger

logger = get_logger("mcp.server")


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _serialise_knowledge_item(item: KnowledgeItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "category": item.category,
        "title": item.title,
        "content": item.content,
        "status": item.status.value,
        "relevance_score": round(item.relevance_score, 3),
        "evidence": item.evidence,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def _serialise_code_chunk(chunk: CodeChunk) -> dict[str, Any]:
    return {
        "file_path": chunk.file_path,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "language": chunk.language,
        "content": chunk.content,
        "relevance_score": round(chunk.relevance_score, 3),
        "summary": chunk.summary,
    }


def _serialise_warning(warning: Warning) -> dict[str, Any]:
    return {
        "severity": warning.severity,
        "category": warning.category,
        "message": warning.message,
        "constraint_id": warning.constraint_id,
        "evidence": warning.evidence,
        "suggested_action": warning.suggested_action,
    }


def _serialise_project_summary(summary: ProjectSummary) -> dict[str, Any]:
    return {
        "name": summary.name,
        "description": summary.description,
        "goals": summary.goals,
        "tech_stack": summary.tech_stack,
        "key_decisions": summary.key_decisions,
        "active_constraints": summary.active_constraints,
        "last_updated": summary.last_updated.isoformat(),
    }


def _serialise_context(ctx: ProjectContext) -> dict[str, Any]:
    return {
        "task": ctx.task,
        "token_count": ctx.token_count,
        "token_budget": ctx.token_budget,
        "retrieval_notes": ctx.retrieval_notes,
        "project_summary": (
            _serialise_project_summary(ctx.project_summary)
            if ctx.project_summary
            else None
        ),
        "knowledge_items": [_serialise_knowledge_item(k) for k in ctx.knowledge_items],
        "code_chunks": [_serialise_code_chunk(c) for c in ctx.code_chunks],
        "warnings": [_serialise_warning(w) for w in ctx.warnings],
    }


def _serialise_audit(report: AuditReport) -> dict[str, Any]:
    return {
        "stale_items": [_serialise_knowledge_item(i) for i in report.stale_items],
        "contradicted_items": [_serialise_knowledge_item(i) for i in report.contradicted_items],
        "missing_evidence": [_serialise_knowledge_item(i) for i in report.missing_evidence],
        "recommendations": report.recommendations,
        "timestamp": report.timestamp.isoformat(),
    }


# ---------------------------------------------------------------------------
# MCP server factory
# ---------------------------------------------------------------------------


def create_server() -> fastmcp.FastMCP:
    """
    Create and configure the ProjectMind FastMCP server.

    Returns a ``FastMCP`` instance with all tools registered.
    Calling ``mcp.run()`` starts the server.
    """
    settings = get_settings()
    mcp = fastmcp.FastMCP(
        name="ProjectMind",
        version="0.1.0",
        instructions=(
            "ProjectMind is a local project intelligence layer for AI coding agents. "
            "Use its tools to understand the project's goals, architecture decisions, "
            "constraints, and relevant code before making changes. "
            "Always call get_project_context() first for any non-trivial task."
        ),
    )

    # -------------------------------------------------------------------------
    # Tool 1: get_project_summary
    # -------------------------------------------------------------------------

    @mcp.tool()
    def get_project_summary() -> dict[str, Any]:
        """
        Get a high-level summary of the project.

        Returns the project's name, description, goals, tech stack,
        key architectural decisions, and active constraints.

        Use this to orient yourself before starting work on a new task,
        or when you need to understand what this project is trying to achieve.

        Returns:
            dict with keys: name, description, goals, tech_stack,
            key_decisions, active_constraints, last_updated
        """
        logger.info("MCP tool called: get_project_summary")
        try:
            core = get_core()
            summary = core.project_memory.get_project_summary()
            return _serialise_project_summary(summary)
        except RuntimeError as e:
            logger.error("get_project_summary failed: %s", e)
            raise

    # -------------------------------------------------------------------------
    # Tool 2: search_project_knowledge
    # -------------------------------------------------------------------------

    @mcp.tool()
    def search_project_knowledge(
        query: str,
        limit: int = 10,
        categories: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search the project's knowledge base using natural language.

        Searches across goals, architecture decisions, constraints,
        history, and other knowledge captured in project memory.

        Examples:
            search_project_knowledge("Why was PostgreSQL chosen?")
            search_project_knowledge("authentication", categories=["constraint"])
            search_project_knowledge("database migration strategy", limit=5)

        Args:
            query:      Natural language query to search with.
            limit:      Maximum number of results to return (default: 10).
            categories: Optional filter. One or more of:
                        "goal", "architecture", "decision",
                        "constraint", "history"

        Returns:
            List of knowledge items, each with:
            id, category, title, content, status (current/stale/contradicted),
            relevance_score, evidence, created_at, updated_at
        """
        logger.info("MCP tool called: search_project_knowledge(query=%r, limit=%d)", query, limit)
        try:
            core = get_core()
            items = core.project_memory.search_knowledge(
                query=query,
                limit=limit,
                categories=categories,
            )
            return [_serialise_knowledge_item(item) for item in items]
        except RuntimeError as e:
            logger.error("search_project_knowledge failed: %s", e)
            raise

    # -------------------------------------------------------------------------
    # Tool 3: get_relevant_code
    # -------------------------------------------------------------------------

    @mcp.tool()
    def get_relevant_code(
        query: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Retrieve code chunks most relevant to a query.

        Uses Member 1 (CodeIntelligence) to find functions, classes,
        and code sections semantically related to your query.

        Examples:
            get_relevant_code("authentication middleware")
            get_relevant_code("database connection pool setup")
            get_relevant_code("user registration flow", limit=3)

        Args:
            query: Natural language or code snippet to match against.
            limit: Maximum code chunks to return (default: 5).

        Returns:
            List of code chunks, each with:
            file_path, start_line, end_line, language,
            content, relevance_score, summary
        """
        logger.info("MCP tool called: get_relevant_code(query=%r, limit=%d)", query, limit)
        try:
            core = get_core()
            chunks = core.code_intelligence.get_related_code(query=query, limit=limit)
            return [_serialise_code_chunk(chunk) for chunk in chunks]
        except RuntimeError as e:
            logger.error("get_relevant_code failed: %s", e)
            raise

    # -------------------------------------------------------------------------
    # Tool 4: get_project_context  (the primary tool for AI agents)
    # -------------------------------------------------------------------------

    @mcp.tool()
    def get_project_context(
        task: str,
        token_budget: int | None = None,
        include_code: bool = True,
    ) -> dict[str, Any]:
        """
        Get the minimum-sufficient context for an AI agent to work on a task.

        This is the primary tool to call before starting any non-trivial task.
        It combines knowledge from all three ProjectMind members to produce a
        token-budgeted context package containing:
          - Relevant project knowledge (goals, decisions, constraints)
          - Relevant code chunks
          - Active warnings (constraint violations, risk flags)
          - A project summary

        The retrieval algorithm (Member 3) ensures that the most important
        information is prioritised within the token budget.

        Examples:
            get_project_context("I want to remove the authentication check from /api/users")
            get_project_context("Add a new payment provider integration", token_budget=6000)
            get_project_context("Refactor the database layer", include_code=True)

        Args:
            task:         Description of the task you are about to perform.
            token_budget: Max tokens to include (defaults to configured budget).
            include_code: Whether to include code chunks (default: True).

        Returns:
            dict with keys:
              task, token_count, token_budget, retrieval_notes,
              project_summary, knowledge_items, code_chunks, warnings
        """
        logger.info("MCP tool called: get_project_context(task=%r)", task)
        try:
            settings = get_settings()
            budget = token_budget or settings.token_budget
            core = get_core()
            ctx = core.context_retriever.get_context(
                task=task,
                token_budget=budget,
                include_code=include_code,
            )
            return _serialise_context(ctx)
        except RuntimeError as e:
            logger.error("get_project_context failed: %s", e)
            raise

    # -------------------------------------------------------------------------
    # Tool 5: get_project_status
    # -------------------------------------------------------------------------

    @mcp.tool()
    def get_project_status() -> dict[str, Any]:
        """
        Get the current status of the ProjectMind installation.

        Returns information about:
          - Whether the code index is up to date
          - Memory engine health and item counts
          - Module availability (which members are registered)
          - Last indexed timestamp

        Use this to check if ProjectMind is functioning correctly
        before relying on its context for a critical task.

        Returns:
            dict with keys:
              memory_status, index_last_updated, modules_available,
              is_fully_configured, health_checks (summary)
        """
        logger.info("MCP tool called: get_project_status")
        try:
            from projectmind.platform.health.doctor import (
                check_database,
                check_index_freshness,
                check_memory_integrity,
                run_doctor,
            )

            core = get_core()
            status: dict[str, Any] = {
                "modules_available": core.available_modules(),
                "is_fully_configured": core.is_fully_configured(),
            }

            # Memory status (if available)
            if core._project_memory is not None:
                mem = core.project_memory.get_status()
                status["memory_status"] = {
                    "total_items": mem.total_items,
                    "current_items": mem.current_items,
                    "stale_items": mem.stale_items,
                    "contradicted_items": mem.contradicted_items,
                    "is_healthy": mem.is_healthy,
                    "last_audit": mem.last_audit.isoformat() if mem.last_audit else None,
                }
            else:
                status["memory_status"] = None

            # Index freshness
            if core._code_intelligence is not None:
                last = core.code_intelligence.get_last_indexed()
                status["index_last_updated"] = last.isoformat() if last else None
            else:
                status["index_last_updated"] = None

            # Quick health check summary
            quick_checks = run_doctor(checks=[
                check_database,
                check_index_freshness,
                check_memory_integrity,
            ])
            status["health_checks"] = [
                {"name": c.name, "status": c.status.value, "message": c.message}
                for c in quick_checks.checks
            ]

            return status
        except RuntimeError as e:
            logger.error("get_project_status failed: %s", e)
            raise

    # -------------------------------------------------------------------------
    # Tool 6: audit_project
    # -------------------------------------------------------------------------

    @mcp.tool()
    def audit_project() -> dict[str, Any]:
        """
        Audit project memory for stale, outdated, or contradicted knowledge.

        Calls Member 2 (ProjectMemory) to analyse the knowledge base and
        identify items that may no longer reflect reality, have conflicting
        information, or lack supporting evidence.

        Use this periodically to keep the knowledge base accurate, or
        before starting a major refactor to understand potential conflicts.

        Returns:
            dict with keys:
              stale_items     — items that may be outdated
              contradicted_items — items with conflicting information
              missing_evidence   — items without supporting code evidence
              recommendations    — suggested actions
              timestamp
        """
        logger.info("MCP tool called: audit_project")
        try:
            core = get_core()
            report = core.project_memory.audit_memory()
            return _serialise_audit(report)
        except RuntimeError as e:
            logger.error("audit_project failed: %s", e)
            raise

    # -------------------------------------------------------------------------
    # Tool 7: get_project_warnings
    # -------------------------------------------------------------------------

    @mcp.tool()
    def get_project_warnings(task: str) -> list[dict[str, Any]]:
        """
        Get warnings and risk flags relevant to a specific task.

        Calls Member 3 (ContextRetriever) to identify constraints, decisions,
        or architectural rules that may be violated or affected by the
        described task.

        Examples:
            get_project_warnings("Remove the authentication middleware")
            get_project_warnings("Add direct database access in the API layer")
            get_project_warnings("Change the user password hashing algorithm")

        Args:
            task: Description of the task you are considering.

        Returns:
            List of warnings, each with:
            severity (low/medium/high/critical), category, message,
            constraint_id, evidence, suggested_action
        """
        logger.info("MCP tool called: get_project_warnings(task=%r)", task)
        try:
            core = get_core()
            warnings = core.context_retriever.get_relevant_warnings(task=task)
            return [_serialise_warning(w) for w in warnings]
        except RuntimeError as e:
            logger.error("get_project_warnings failed: %s", e)
            raise

    return mcp
