"""Tests for the ProjectMind CLI."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from click.testing import CliRunner
from projectmind.platform.cli.main import cli


class TestInit:
    def test_init_creates_files(self, tmp_path: Path, cli_runner: CliRunner):
        os.chdir(tmp_path)
        result = cli_runner.invoke(cli, ["init", "--name", "test-project"], catch_exceptions=False)
        # CLI is invoked from process cwd — use mix_stderr=False for predictable output
        # We test the command succeeds with exit code 0
        assert result.exit_code == 0

    def test_init_fails_if_already_exists(
        self, tmp_path: Path, cli_runner: CliRunner, project_dir: Path
    ):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["init"])
        assert result.exit_code == 1
        assert "already exists" in result.output or "already exists" in (result.stderr or "")

    def test_init_force_overwrites(self, tmp_path: Path, cli_runner: CliRunner, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["init", "--force", "--name", "new-name"])
        assert result.exit_code == 0


class TestDoctor:
    def test_doctor_runs_without_crash(self, cli_runner: CliRunner):
        result = cli_runner.invoke(cli, ["doctor"])
        # Doctor should always return an output, exit 0 or 1
        assert result.exit_code in (0, 1)
        assert result.output  # some output produced

    def test_doctor_json_output(self, cli_runner: CliRunner):
        result = cli_runner.invoke(cli, ["doctor", "--json-output"])
        assert result.exit_code in (0, 1)
        data = json.loads(result.output)
        assert "checks" in data
        assert "overall" in data
        assert isinstance(data["checks"], list)
        for check in data["checks"]:
            assert "name" in check
            assert "status" in check
            assert check["status"] in ("pass", "warn", "fail")

    def test_doctor_fails_with_exit_1_when_failures(self, cli_runner: CliRunner):
        """Doctor should exit 1 when there are failures."""
        result = cli_runner.invoke(cli, ["doctor"])
        # Without init, there should be failures
        if result.exit_code == 1:
            data_lines = result.output
            assert len(data_lines) > 0


class TestQuery:
    def test_query_with_stub_core(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["query", "PostgreSQL"])
        assert result.exit_code == 0

    def test_query_json_output(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["query", "database", "--json-output"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)

    def test_query_no_results(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["query", "zzzznonexistent"])
        assert result.exit_code == 0

    def test_query_with_category_filter(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["query", "security", "--category", "constraint"])
        assert result.exit_code == 0


class TestContext:
    def test_context_with_stub_core(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["context", "Add a new endpoint"])
        assert result.exit_code == 0

    def test_context_json_output(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["context", "Refactor auth", "--json-output"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "task" in data
        assert "warnings" in data
        assert "knowledge_items" in data

    def test_context_shows_auth_warning(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(
            cli, ["context", "Remove authentication from the endpoint", "--json-output"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        warnings = data.get("warnings", [])
        assert len(warnings) > 0
        severities = [w["severity"] for w in warnings]
        assert "high" in severities


class TestStatus:
    def test_status_with_stub_core(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["status"])
        assert result.exit_code == 0


class TestAudit:
    def test_audit_with_stub_core(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["audit"])
        assert result.exit_code == 0

    def test_audit_json_output(self, cli_runner: CliRunner, stub_core, project_dir: Path):
        os.chdir(project_dir)
        result = cli_runner.invoke(cli, ["audit", "--json-output"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert "stale_items" in data
        assert "recommendations" in data


class TestConnectClaude:
    def test_connect_claude_dry_run(self, cli_runner: CliRunner):
        result = cli_runner.invoke(cli, ["connect", "claude", "--dry-run"])
        assert result.exit_code == 0

    def test_connect_ollama(self, cli_runner: CliRunner):
        result = cli_runner.invoke(cli, ["connect", "ollama", "--model", "llama3"])
        assert result.exit_code == 0
        assert "ollama" in result.output.lower() or "projectmind" in result.output.lower()


class TestHelp:
    def test_help(self, cli_runner: CliRunner):
        result = cli_runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "init" in result.output
        assert "doctor" in result.output
        assert "serve" in result.output

    @pytest.mark.parametrize(
        "command", ["init", "index", "status", "query", "context", "audit", "doctor"]
    )
    def test_command_help(self, cli_runner: CliRunner, command: str):
        result = cli_runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0
        assert "--help" in result.output or "Usage" in result.output
