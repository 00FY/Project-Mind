"""Integration tests between Member 1 and the shared ProjectMind core."""

from pathlib import Path

from projectmind.code_intelligence.service import CodeIntelligenceService
from projectmind.core.interfaces import ProjectMindCore


def create_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_member1_service_registers_with_projectmind_core(
    tmp_path: Path,
) -> None:
    create_file(
        tmp_path / "src" / "auth.py",
        """class AuthService:
    def login(self):
        return True
""",
    )

    code_intelligence = CodeIntelligenceService(tmp_path)

    core = ProjectMindCore(
        code_intelligence=code_intelligence,
    )

    assert core.available_modules() == {
        "code_intelligence": True,
        "project_memory": False,
        "context_retriever": False,
    }

    result = core.code_intelligence.index_project(str(tmp_path))

    assert result.files_indexed == 1

    summary = core.code_intelligence.get_file_summary(
        "src/auth.py"
    )

    assert "AuthService" in summary.classes
