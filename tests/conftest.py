"""
Shared pytest fixtures for all ProjectMind tests.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from projectmind.core.interfaces import ProjectMindCore, set_core
from projectmind.platform.config.settings import reset_settings
from projectmind.platform.logging.setup import reset_logging
from tests.stubs import StubCodeIntelligence, StubContextRetriever, StubProjectMemory


@pytest.fixture(autouse=True)
def reset_global_state(tmp_path: Path):
    """
    Reset all global singletons before each test.
    Prevents state leakage between tests.
    """
    reset_settings()
    reset_logging()
    yield
    reset_settings()
    reset_logging()


@pytest.fixture()
def stub_core() -> ProjectMindCore:
    """A fully-configured ProjectMindCore with stub implementations."""
    memory = StubProjectMemory()
    code_intel = StubCodeIntelligence()
    retriever = StubContextRetriever(memory=memory, code_intel=code_intel)
    core = ProjectMindCore(
        code_intelligence=code_intel,
        project_memory=memory,
        context_retriever=retriever,
    )
    set_core(core)
    return core


@pytest.fixture()
def empty_core() -> ProjectMindCore:
    """A ProjectMindCore with no modules registered (tests error handling)."""
    core = ProjectMindCore()
    set_core(core)
    return core


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    """A temporary project directory with .projectmind/ initialised."""
    mem_dir = tmp_path / ".projectmind"
    mem_dir.mkdir()
    (mem_dir / "logs").mkdir()
    (mem_dir / ".gitignore").write_text("*\n!.gitignore\n")

    config = tmp_path / "projectmind.toml"
    config.write_text(
        f'[project]\nname = "test-project"\nroot = "."\nmemory_dir = ".projectmind"\n'
        f'[retrieval]\ntoken_budget = 4000\n'
        f'[mcp]\ntransport = "stdio"\nport = 3333\n'
        f'[logging]\nlevel = "WARNING"\n'
    )
    return tmp_path


@pytest.fixture()
def cli_runner():
    """Click test runner."""
    from click.testing import CliRunner
    return CliRunner()
