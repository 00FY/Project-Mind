"""Integration tests for Member 3 Context & Retrieval service."""

from pathlib import Path
import pytest

from projectmind.code_intelligence.service import CodeIntelligenceService
from projectmind.core.interfaces import ProjectMindCore
from projectmind.memory.enums import MemoryType
from projectmind.memory.models import Memory, utc_now
from projectmind.memory.project_memory import SQLiteProjectMemory
from projectmind.memory.repository import MemoryRepository
from projectmind.retrieval.service import RetrievalService


@pytest.fixture
def temp_repo(tmp_path: Path) -> Path:
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    auth_file = src_dir / "auth.py"
    auth_file.write_text(
        """
class AuthService:
    def login(self, username, password):
        return True

    def logout(self, user_id):
        pass
""",
        encoding="utf-8",
    )
    return tmp_path


def test_retrieval_service_full_integration(temp_repo: Path, tmp_path: Path):
    ci_service = CodeIntelligenceService(temp_repo)
    ci_service.index_project(str(temp_repo))

    db_path = tmp_path / "memory.db"
    repo = MemoryRepository(db_path)
    now = utc_now()

    from projectmind.memory.evidence import Evidence, EvidenceKind

    repo.create_evidence(
        Evidence(
            id="ev-001",
            kind=EvidenceKind.CODE,
            file_path="src/auth.py",
            description="Auth implementation",
        )
    )

    mem = Memory(
        id="mem-1",
        type=MemoryType.ARCHITECTURE,
        content="Authentication is handled through AuthService in src/auth.py",
        subject="AuthService",
        importance=0.8,
        confidence=0.9,
        created_at=now,
        updated_at=now,
        evidence=["ev-001"],
    )
    repo.create_memory(mem)

    memory_service = SQLiteProjectMemory(repo)

    retrieval_service = RetrievalService(
        code_intelligence=ci_service,
        project_memory=memory_service,
    )

    core = ProjectMindCore(
        code_intelligence=ci_service,
        project_memory=memory_service,
        context_retriever=retrieval_service,
    )

    assert core.context_retriever is not None

    context = core.context_retriever.get_context(
        task="How does login work in AuthService?",
        token_budget=2000,
        include_code=True,
    )

    assert context.task == "How does login work in AuthService?"
    assert len(context.knowledge_items) >= 1
    assert len(context.code_chunks) >= 1
    assert any("AuthService" in k.content for k in context.knowledge_items)
    assert context.token_count > 0

    warnings = core.context_retriever.get_relevant_warnings(
        "Fix login password authentication issue"
    )
    assert len(warnings) >= 1
    assert warnings[0].category == "security"
