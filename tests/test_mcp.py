"""Tests for the ProjectMind MCP server tools."""

from __future__ import annotations

import pytest

from projectmind.core.interfaces import ProjectMindCore, set_core
from projectmind.platform.mcp.server import create_server
from tests.stubs import StubCodeIntelligence, StubContextRetriever, StubProjectMemory


@pytest.fixture()
def mcp_server(stub_core):
    """Create a FastMCP server instance with stub core."""
    return create_server()


class TestGetProjectSummary:
    def test_returns_summary(self, mcp_server, stub_core):
        # Get the tool function directly from FastMCP
        tool_fn = _get_tool(mcp_server, "get_project_summary")
        result = tool_fn()

        assert isinstance(result, dict)
        assert "name" in result
        assert "description" in result
        assert "goals" in result
        assert isinstance(result["goals"], list)
        assert "tech_stack" in result
        assert "key_decisions" in result
        assert "active_constraints" in result
        assert "last_updated" in result

    def test_raises_on_missing_module(self, mcp_server, empty_core):
        tool_fn = _get_tool(mcp_server, "get_project_summary")
        with pytest.raises(RuntimeError, match="ProjectMemory"):
            tool_fn()


class TestSearchProjectKnowledge:
    def test_returns_list(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "search_project_knowledge")
        result = tool_fn(query="PostgreSQL")

        assert isinstance(result, list)
        if result:
            item = result[0]
            assert "id" in item
            assert "title" in item
            assert "content" in item
            assert "status" in item
            assert "category" in item
            assert "relevance_score" in item

    def test_limit_respected(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "search_project_knowledge")
        result = tool_fn(query="", limit=2)
        assert len(result) <= 2

    def test_category_filter(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "search_project_knowledge")
        result = tool_fn(query="", categories=["constraint"])
        categories = {item["category"] for item in result}
        assert categories.issubset({"constraint"})

    def test_empty_query_returns_items(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "search_project_knowledge")
        result = tool_fn(query="")
        # Empty query should still return items (no filtering)
        assert isinstance(result, list)


class TestGetRelevantCode:
    def test_returns_code_chunks(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_relevant_code")
        result = tool_fn(query="authentication")

        assert isinstance(result, list)
        assert len(result) > 0
        chunk = result[0]
        assert "file_path" in chunk
        assert "start_line" in chunk
        assert "end_line" in chunk
        assert "content" in chunk
        assert "language" in chunk
        assert "relevance_score" in chunk

    def test_limit_respected(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_relevant_code")
        result = tool_fn(query="database", limit=2)
        assert len(result) <= 2


class TestGetProjectContext:
    def test_returns_context(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_context")
        result = tool_fn(task="Add a new user endpoint")

        assert isinstance(result, dict)
        assert result["task"] == "Add a new user endpoint"
        assert "token_count" in result
        assert "token_budget" in result
        assert "knowledge_items" in result
        assert "code_chunks" in result
        assert "warnings" in result
        assert isinstance(result["knowledge_items"], list)
        assert isinstance(result["code_chunks"], list)
        assert isinstance(result["warnings"], list)

    def test_auth_warning_generated(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_context")
        result = tool_fn(task="Remove authentication from public endpoint")

        warnings = result["warnings"]
        assert len(warnings) > 0
        high_warnings = [w for w in warnings if w["severity"] in ("high", "critical")]
        assert len(high_warnings) > 0

    def test_token_budget_respected(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_context")
        result = tool_fn(task="Refactor the codebase", token_budget=2000)

        assert result["token_budget"] == 2000
        assert result["token_count"] <= 2000

    def test_no_code_when_include_code_false(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_context")
        result = tool_fn(task="Explain the architecture", include_code=False)

        assert result["code_chunks"] == []


class TestGetProjectStatus:
    def test_returns_status(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_status")
        result = tool_fn()

        assert isinstance(result, dict)
        assert "modules_available" in result
        assert "is_fully_configured" in result
        modules = result["modules_available"]
        assert "code_intelligence" in modules
        assert "project_memory" in modules
        assert "context_retriever" in modules
        assert all(modules.values())  # all True with stub_core

    def test_fully_configured_true(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_status")
        result = tool_fn()
        assert result["is_fully_configured"] is True

    def test_not_fully_configured_without_modules(self, mcp_server, empty_core):
        tool_fn = _get_tool(mcp_server, "get_project_status")
        result = tool_fn()
        assert result["is_fully_configured"] is False


class TestAuditProject:
    def test_returns_audit_report(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "audit_project")
        result = tool_fn()

        assert isinstance(result, dict)
        assert "stale_items" in result
        assert "contradicted_items" in result
        assert "missing_evidence" in result
        assert "recommendations" in result
        assert isinstance(result["stale_items"], list)

    def test_stale_items_detected(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "audit_project")
        result = tool_fn()

        # StubProjectMemory has 1 stale item
        assert len(result["stale_items"]) >= 1


class TestGetProjectWarnings:
    def test_returns_list(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_warnings")
        result = tool_fn(task="Add a feature")

        assert isinstance(result, list)

    def test_auth_warning_triggered(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_warnings")
        result = tool_fn(task="Remove authentication check from /api/users")

        assert len(result) > 0
        severities = {w["severity"] for w in result}
        assert "high" in severities or "critical" in severities

    def test_architecture_warning_triggered(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_warnings")
        result = tool_fn(task="Run direct database queries from the API controller")

        assert len(result) > 0
        categories = {w["category"] for w in result}
        assert "architecture" in categories

    def test_warning_structure(self, mcp_server, stub_core):
        tool_fn = _get_tool(mcp_server, "get_project_warnings")
        result = tool_fn(task="Remove the auth middleware")

        if result:
            w = result[0]
            assert "severity" in w
            assert "category" in w
            assert "message" in w
            assert w["severity"] in ("low", "medium", "high", "critical")


# ---------------------------------------------------------------------------
# Helper to extract tool functions from FastMCP
# ---------------------------------------------------------------------------

def _get_tool(mcp_server, tool_name: str):
    """
    Extract the raw tool function from a FastMCP server for direct testing.
    FastMCP stores tools in _tools dict.
    """
    import asyncio
    
    tool_fn = None
    if hasattr(mcp_server, "_tools"):
        tool = mcp_server._tools.get(tool_name)
        if tool:
            tool_fn = tool.fn if hasattr(tool, "fn") else tool
    elif hasattr(mcp_server, "get_tool"):
        tool = mcp_server.get_tool(tool_name)
        if tool:
            tool_fn = tool.fn if hasattr(tool, "fn") else tool
    else:
        for attr_name in dir(mcp_server):
            obj = getattr(mcp_server, attr_name, None)
            if callable(obj) and getattr(obj, "__name__", "") == tool_name:
                tool_fn = obj
                break
                
    if not tool_fn:
        raise AttributeError(f"Tool '{tool_name}' not found in MCP server")
        
    def sync_wrapper(*args, **kwargs):
        res = tool_fn(*args, **kwargs)
        if asyncio.iscoroutine(res):
            return asyncio.run(res)
        return res
        
    return sync_wrapper
