"""
End-to-end integration tests for ProjectMind.

These tests simulate a complete agent workflow:
  1. CLI init
  2. MCP server creation
  3. Tool calls through the MCP server
  4. Config + adapter integration

All tests use stub implementations of Members 1/2/3 so they run
without any real code analysis, database, or AI API calls.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from projectmind.core.interfaces import ProjectMindCore, set_core
from projectmind.platform.cli.main import cli
from projectmind.platform.mcp.server import create_server

from tests.stubs import StubCodeIntelligence, StubContextRetriever, StubProjectMemory


@pytest.fixture()
def full_setup(tmp_path: Path):
    """
    Full integration setup:
    - temp project directory initialised
    - settings loaded
    - stub core registered
    - MCP server created
    """
    os.chdir(tmp_path)

    # Initialise project via CLI
    runner = CliRunner()
    result = runner.invoke(cli, ["init", "--name", "integration-test-project"])
    assert result.exit_code == 0, f"Init failed: {result.output}"

    # Load the generated config
    from projectmind.platform.config.settings import load_settings
    settings = load_settings(tmp_path / "projectmind.toml")

    # Register stub core
    memory = StubProjectMemory()
    code_intel = StubCodeIntelligence()
    retriever = StubContextRetriever(memory=memory, code_intel=code_intel)
    core = ProjectMindCore(
        code_intelligence=code_intel,
        project_memory=memory,
        context_retriever=retriever,
    )
    set_core(core)

    mcp = create_server()
    return {"tmp_path": tmp_path, "settings": settings, "core": core, "mcp": mcp, "runner": runner}


class TestFullWorkflow:
    """Simulates the complete agent workflow end-to-end."""

    def test_init_creates_correct_structure(self, full_setup):
        tmp_path = full_setup["tmp_path"]
        assert (tmp_path / ".projectmind").exists()
        assert (tmp_path / ".projectmind" / "logs").exists()
        assert (tmp_path / "projectmind.toml").exists()
        assert (tmp_path / ".projectmind" / ".gitignore").exists()

    def test_doctor_runs_after_init(self, full_setup):
        runner = full_setup["runner"]
        result = runner.invoke(cli, ["doctor", "--json-output"])
        data = json.loads(result.output)
        # At minimum, project directory check should pass
        check_names = {c["name"] for c in data["checks"]}
        assert "Project directory" in check_names
        assert "Configuration file" in check_names

    def test_agent_auth_scenario(self, full_setup):
        """
        Simulate: AI agent asks 'Can I remove auth from this endpoint?'
        Expected: ProjectMind returns a HIGH severity warning.
        """
        from tests.test_mcp import _get_tool
        mcp = full_setup["mcp"]

        tool_fn = _get_tool(mcp, "get_project_context")
        context = tool_fn(task="I want to remove the authentication check from this endpoint")

        # Should have a high-severity auth warning
        warnings = context["warnings"]
        assert len(warnings) > 0, "Expected auth warning but got none"
        high_warnings = [w for w in warnings if w["severity"] in ("high", "critical")]
        assert len(high_warnings) > 0, f"Expected high severity warning, got: {warnings}"
        assert any("SEC-07" in w.get("constraint_id", "") for w in warnings), \
            "Expected SEC-07 constraint reference"

    def test_agent_knowledge_search_scenario(self, full_setup):
        """
        Simulate: AI agent asks 'Why did we choose PostgreSQL?'
        Expected: Decision item returned with rationale.
        """
        from tests.test_mcp import _get_tool
        mcp = full_setup["mcp"]

        tool_fn = _get_tool(mcp, "search_project_knowledge")
        results = tool_fn(query="Why did we choose PostgreSQL?")

        assert len(results) > 0
        titles = [r["title"] for r in results]
        assert any("PostgreSQL" in t for t in titles), f"Expected PostgreSQL result, got: {titles}"

    def test_agent_context_token_budget(self, full_setup):
        """
        Simulate: Agent with tight token budget.
        Expected: Context stays within budget.
        """
        from tests.test_mcp import _get_tool
        mcp = full_setup["mcp"]

        budget = 500
        tool_fn = _get_tool(mcp, "get_project_context")
        context = tool_fn(task="Explain the architecture", token_budget=budget)

        assert context["token_budget"] == budget
        assert context["token_count"] <= budget

    def test_index_command(self, full_setup):
        """Simulate running 'projectmind index'."""
        runner = full_setup["runner"]
        result = runner.invoke(cli, ["index"])
        assert result.exit_code == 0

    def test_audit_command(self, full_setup):
        """Simulate running 'projectmind audit'."""
        runner = full_setup["runner"]
        result = runner.invoke(cli, ["audit", "--json-output"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "stale_items" in data

    def test_status_command(self, full_setup):
        """Simulate running 'projectmind status'."""
        runner = full_setup["runner"]
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0

    def test_claude_dry_run(self, full_setup):
        """Simulate 'projectmind connect claude --dry-run'."""
        runner = full_setup["runner"]
        result = runner.invoke(cli, ["connect", "claude", "--dry-run"])
        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "projectmind" in output_lower


class TestAdapterIntegration:
    def test_claude_adapter_formats_context(self, full_setup):
        from projectmind.platform.adapters.claude_desktop import ClaudeDesktopAdapter

        from tests.test_mcp import _get_tool

        mcp = full_setup["mcp"]
        adapter = ClaudeDesktopAdapter()

        context = _get_tool(mcp, "get_project_context")(task="Add new feature")
        formatted = adapter.format_context(context)

        assert isinstance(formatted, str)
        assert "Task:" in formatted
        assert "Tokens:" in formatted

    def test_ollama_adapter_formats_context(self, full_setup):
        from projectmind.platform.adapters.ollama import OllamaAdapter

        from tests.test_mcp import _get_tool

        mcp = full_setup["mcp"]
        adapter = OllamaAdapter()

        context = _get_tool(mcp, "get_project_context")(task="Refactor auth")
        formatted = adapter.format_context(context)

        assert isinstance(formatted, str)
        assert "PROJECT CONTEXT" in formatted

    def test_adapter_registry(self):
        # Import adapters to trigger @register_adapter decorators
        from projectmind.platform.adapters.base import get_adapter, list_adapters

        available = list_adapters()
        assert "claude" in available
        assert "ollama" in available

        claude = get_adapter("claude")
        assert claude.name == "Claude Desktop"

    def test_adapter_warning_format(self, full_setup):
        from projectmind.platform.adapters.claude_desktop import ClaudeDesktopAdapter

        from tests.test_mcp import _get_tool

        mcp = full_setup["mcp"]
        adapter = ClaudeDesktopAdapter()

        warnings = _get_tool(mcp, "get_project_warnings")(
            task="Remove authentication check"
        )
        formatted = adapter.format_warning(warnings)

        assert isinstance(formatted, str)
        if warnings:
            assert "WARNING" in formatted.upper() or "HIGH" in formatted.upper()


class TestConfigIntegration:
    def test_config_loaded_from_toml(self, full_setup):
        settings = full_setup["settings"]
        assert settings.project.name == "integration-test-project"
        assert settings.retrieval.token_budget == 8000
        assert settings.mcp.transport == "stdio"

    def test_env_override(self, full_setup, monkeypatch):
        monkeypatch.setenv("PROJECTMIND_TOKEN_BUDGET", "1234")
        monkeypatch.setenv("PROJECTMIND_LOG_LEVEL", "DEBUG")
        from projectmind.platform.config.settings import load_settings, reset_settings
        reset_settings()
        settings = load_settings()
        assert settings.retrieval.token_budget == 1234
        assert settings.logging.level == "DEBUG"


class TestErrorHandling:
    def test_query_without_init_exits_gracefully(self, tmp_path: Path):
        os.chdir(tmp_path)
        runner = CliRunner()
        result = runner.invoke(cli, ["query", "anything"])
        assert result.exit_code == 1

    def test_context_without_module_exits_gracefully(self, tmp_path: Path, project_dir: Path):
        os.chdir(project_dir)
        # empty_core has no modules
        set_core(ProjectMindCore())
        runner = CliRunner()
        result = runner.invoke(cli, ["context", "some task"])
        assert result.exit_code == 1

    def test_doctor_always_returns_data(self, full_setup):
        """Doctor must always produce output even in edge cases."""
        runner = full_setup["runner"]
        result = runner.invoke(cli, ["doctor", "--json-output"])
        # Must parse as valid JSON regardless
        data = json.loads(result.output)
        assert "checks" in data
        assert len(data["checks"]) > 0
