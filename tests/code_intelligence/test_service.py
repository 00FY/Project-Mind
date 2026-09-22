"""Tests for the Member 1 Code Intelligence service."""

from pathlib import Path

from projectmind.code_intelligence.service import CodeIntelligenceService


def create_file(path: Path, content: str) -> None:
    """Create a test file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_service_indexes_project(tmp_path: Path) -> None:
    """Service should index a project through the shared interface."""
    create_file(
        tmp_path / "src" / "auth.py",
        """class AuthService:
    def login(self):
        return True
""",
    )

    service = CodeIntelligenceService(tmp_path)
    result = service.index_project(str(tmp_path))

    assert result.files_indexed == 1
    assert result.errors == []
    assert service.get_last_indexed() is not None


def test_service_returns_file_summary(tmp_path: Path) -> None:
    """Service should provide a summary after indexing."""
    create_file(
        tmp_path / "src" / "auth.py",
        """import sqlite3

class AuthService:
    def login(self):
        return True

def validate_token(token):
    return True
""",
    )

    service = CodeIntelligenceService(tmp_path)
    service.index_project(str(tmp_path))

    summary = service.get_file_summary("src/auth.py")

    assert summary.path == "src/auth.py"
    assert summary.language == "python"
    assert "AuthService" in summary.classes
    assert "validate_token" in summary.functions
    assert "import sqlite3" in summary.imports


def test_service_finds_related_code(tmp_path: Path) -> None:
    """Service should return basic code matches."""
    create_file(
        tmp_path / "src" / "auth.py",
        """class AuthService:
    def login(self):
        return True
""",
    )

    service = CodeIntelligenceService(tmp_path)
    service.index_project(str(tmp_path))

    results = service.get_related_code("AuthService")

    assert len(results) == 1
    assert results[0].file_path == "src/auth.py"
    assert results[0].start_line == 1
    assert "class AuthService" in results[0].content


def test_service_git_changes_are_not_implemented_yet(
    tmp_path: Path,
) -> None:
    """Git changes remain empty until the Git tracker is implemented."""
    service = CodeIntelligenceService(tmp_path)

    assert service.get_git_changes() == []
