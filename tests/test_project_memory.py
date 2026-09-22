from datetime import datetime, timezone

from projectmind.memory.enums import MemoryStatus, MemoryType
from projectmind.memory.models import Memory
from projectmind.memory.project_memory import SQLiteProjectMemory
from projectmind.memory.repository import MemoryRepository
from projectmind.memory.evidence import Evidence, EvidenceKind


def make_memory(
    memory_id: str,
    memory_type: MemoryType,
    content: str,
    *,
    importance: float = 0.5,
    status: MemoryStatus = MemoryStatus.ACTIVE,
    subject: str | None = None,
    evidence: list[str] | None = None,
) -> Memory:
    now = datetime.now(timezone.utc)

    return Memory(
        id=memory_id,
        type=memory_type,
        content=content,
        importance=importance,
        confidence=0.9,
        status=status,
        created_at=now,
        updated_at=now,
        subject=subject,
        evidence=evidence or [],
    )


def make_project_memory(tmp_path) -> SQLiteProjectMemory:
    repository = MemoryRepository(tmp_path / "test.db")
    return SQLiteProjectMemory(repository)


def test_memory_is_exposed_as_knowledge_item(tmp_path):
    project_memory = make_project_memory(tmp_path)

    project_memory.repository.create_evidence(
        Evidence(
            id="evidence-001",
            kind=EvidenceKind.CODE,
            file_path="projectmind/memory/repository.py",
            description="Memory persistence implementation.",
        )
    )

    memory = make_memory(
        "mem-001",
        MemoryType.ARCHITECTURE,
        "The system uses SQLite for persistent project memory.",
        subject="SQLite Persistence",
        evidence=["evidence-001"],
    )

    project_memory.repository.create_memory(memory)

    results = project_memory.search_knowledge("SQLite")

    assert len(results) == 1

    item = results[0]

    assert item.id == "mem-001"
    assert item.category == "architecture"
    assert item.title == "SQLite Persistence"
    assert item.content == memory.content
    assert item.evidence == ["evidence-001"]


def test_search_knowledge_matches_subject_and_content(tmp_path):
    project_memory = make_project_memory(tmp_path)

    project_memory.repository.create_memory(
        make_memory(
            "mem-001",
            MemoryType.ARCHITECTURE,
            "The memory layer persists project knowledge.",
            subject="SQLite Database",
        )
    )

    project_memory.repository.create_memory(
        make_memory(
            "mem-002",
            MemoryType.DECISION,
            "Use evidence-linked memories.",
            subject="Evidence",
        )
    )

    results = project_memory.search_knowledge("SQLite")

    assert [item.id for item in results] == ["mem-001"]


def test_search_knowledge_respects_category_filter(tmp_path):
    project_memory = make_project_memory(tmp_path)

    project_memory.repository.create_memory(
        make_memory(
            "mem-001",
            MemoryType.ARCHITECTURE,
            "SQLite stores project memory.",
        )
    )

    project_memory.repository.create_memory(
        make_memory(
            "mem-002",
            MemoryType.DECISION,
            "Use SQLite for persistence.",
        )
    )

    results = project_memory.search_knowledge(
        "SQLite",
        categories=["architecture"],
    )

    assert len(results) == 1
    assert results[0].id == "mem-001"
    assert results[0].category == "architecture"


def test_project_summary_contains_active_project_information(tmp_path):
    project_memory = make_project_memory(tmp_path)

    project_memory.repository.create_memory(
        make_memory(
            "goal-001",
            MemoryType.GOAL,
            "Maintain persistent project knowledge.",
        )
    )

    project_memory.repository.create_memory(
        make_memory(
            "decision-001",
            MemoryType.DECISION,
            "Use SQLite as the initial persistence layer.",
        )
    )

    project_memory.repository.create_memory(
        make_memory(
            "constraint-001",
            MemoryType.CONSTRAINT,
            "Important memories must have evidence.",
        )
    )

    summary = project_memory.get_project_summary()

    assert summary.name == "ProjectMind"
    assert "Maintain persistent project knowledge." in summary.goals
    assert "Use SQLite as the initial persistence layer." in summary.key_decisions
    assert "Important memories must have evidence." in summary.active_constraints


def test_audit_memory_reports_stale_and_contradicted_items(tmp_path):
    project_memory = make_project_memory(tmp_path)

    project_memory.repository.create_memory(
        make_memory(
            "active-001",
            MemoryType.FACT,
            "Active project fact.",
        )
    )

    project_memory.repository.create_memory(
        make_memory(
            "stale-001",
            MemoryType.FACT,
            "Old project fact.",
            status=MemoryStatus.STALE,
        )
    )

    project_memory.repository.create_memory(
        make_memory(
            "contradicted-001",
            MemoryType.FACT,
            "Contradicted project fact.",
            status=MemoryStatus.CONTRADICTED,
        )
    )

    report = project_memory.audit_memory()

    assert [item.id for item in report.stale_items] == ["stale-001"]
    assert [item.id for item in report.contradicted_items] == [
        "contradicted-001"
    ]


def test_get_status_returns_memory_statistics(tmp_path):
    project_memory = make_project_memory(tmp_path)

    project_memory.repository.create_memory(
        make_memory(
            "active-001",
            MemoryType.FACT,
            "Current fact.",
        )
    )

    project_memory.repository.create_memory(
        make_memory(
            "stale-001",
            MemoryType.FACT,
            "Stale fact.",
            status=MemoryStatus.STALE,
        )
    )

    project_memory.repository.create_memory(
        make_memory(
            "contradicted-001",
            MemoryType.FACT,
            "Contradicted fact.",
            status=MemoryStatus.CONTRADICTED,
        )
    )

    status = project_memory.get_status()

    assert status.total_items == 3
    assert status.current_items == 1
    assert status.stale_items == 1
    assert status.contradicted_items == 1
    assert status.is_healthy is True
    assert status.db_path.endswith("test.db")


def test_is_healthy_returns_true_for_accessible_database(tmp_path):
    project_memory = make_project_memory(tmp_path)

    assert project_memory.is_healthy() is True