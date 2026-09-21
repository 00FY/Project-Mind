"""
Test stubs — concrete implementations of the Member 1/2/3 interfaces
for use in unit and integration tests.

These stubs have deterministic, predictable behaviour so tests can
assert exact outputs without running real code analysis.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from projectmind.core.interfaces import (
    AuditReport,
    CodeChunk,
    CodeIntelligence,
    ContextRetriever,
    FileSummary,
    GitChange,
    IndexResult,
    KnowledgeItem,
    MemoryStatus,
    ProjectContext,
    ProjectMemory,
    ProjectSummary,
    ValidationStatus,
    Warning,
)


# ---------------------------------------------------------------------------
# Member 1 stub
# ---------------------------------------------------------------------------


class StubCodeIntelligence(CodeIntelligence):
    """Deterministic stub for Member 1 — CodeIntelligence."""

    def __init__(self, indexed: bool = True):
        self._indexed = indexed
        self._last_indexed = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc) if indexed else None

    def index_project(self, project_root: str) -> IndexResult:
        self._indexed = True
        self._last_indexed = datetime.now(timezone.utc)
        return IndexResult(
            files_indexed=42,
            files_skipped=3,
            duration_seconds=1.23,
            errors=[],
        )

    def get_file_summary(self, file_path: str) -> FileSummary:
        return FileSummary(
            path=file_path,
            language="python",
            functions=["main", "helper"],
            classes=["MyClass"],
            imports=["os", "sys"],
            summary=f"Summary of {file_path}",
        )

    def get_related_code(self, query: str, limit: int = 5) -> list[CodeChunk]:
        return [
            CodeChunk(
                file_path=f"src/module_{i}.py",
                start_line=10 * i,
                end_line=10 * i + 9,
                content=f"def stub_function_{i}():\n    # Related to: {query}\n    pass",
                language="python",
                relevance_score=0.9 - i * 0.1,
                summary=f"Stub function {i} related to query",
            )
            for i in range(1, min(limit, 4) + 1)
        ]

    def get_git_changes(self, since_commit: str = "HEAD~1") -> list[GitChange]:
        return [
            GitChange(
                file_path="src/auth.py",
                change_type="modified",
                additions=15,
                deletions=3,
                diff_summary="Added JWT validation",
                commit_hash="abc1234",
                commit_message="feat: add JWT validation",
                timestamp=datetime.now(timezone.utc),
            )
        ]

    def get_last_indexed(self) -> datetime | None:
        return self._last_indexed


# ---------------------------------------------------------------------------
# Member 2 stub
# ---------------------------------------------------------------------------


class StubProjectMemory(ProjectMemory):
    """Deterministic stub for Member 2 — ProjectMemory."""

    _ITEMS = [
        KnowledgeItem(
            id="dec-001",
            category="decision",
            title="PostgreSQL chosen as primary database",
            content=(
                "We chose PostgreSQL over MySQL for its JSONB support, "
                "full-text search, and superior ACID compliance."
            ),
            status=ValidationStatus.CURRENT,
            evidence=["ADR-003", "meeting-2024-03-15"],
            relevance_score=0.95,
        ),
        KnowledgeItem(
            id="con-001",
            category="constraint",
            title="SEC-07: All endpoints must require authentication",
            content=(
                "All API endpoints MUST require JWT authentication. "
                "Public endpoints must be explicitly approved by the security team."
            ),
            status=ValidationStatus.CURRENT,
            evidence=["security-policy-v2"],
            relevance_score=0.88,
        ),
        KnowledgeItem(
            id="arch-001",
            category="architecture",
            title="Layered architecture: API → Service → Repository",
            content=(
                "The codebase follows a strict layered architecture. "
                "API layer calls Service layer; Service layer calls Repository. "
                "No direct database access from the API layer."
            ),
            status=ValidationStatus.CURRENT,
            evidence=["ARCH-001"],
            relevance_score=0.82,
        ),
        KnowledgeItem(
            id="goal-001",
            category="goal",
            title="Build a multi-tenant SaaS platform",
            content="The primary goal is to build a scalable multi-tenant SaaS platform.",
            status=ValidationStatus.CURRENT,
            relevance_score=0.75,
        ),
        KnowledgeItem(
            id="dec-002",
            category="decision",
            title="Bcrypt for password hashing [STALE]",
            content="Passwords are hashed with bcrypt with cost factor 12.",
            status=ValidationStatus.STALE,
            relevance_score=0.6,
        ),
    ]

    def get_project_summary(self) -> ProjectSummary:
        return ProjectSummary(
            name="StubProject",
            description="A stub project for testing ProjectMind.",
            goals=["Build scalable SaaS", "Maintain high test coverage"],
            tech_stack=["Python", "PostgreSQL", "FastAPI", "Redis"],
            key_decisions=["PostgreSQL over MySQL", "JWT authentication"],
            active_constraints=["SEC-07: Auth required", "Layered architecture"],
        )

    def search_knowledge(
        self,
        query: str,
        limit: int = 10,
        categories: list[str] | None = None,
    ) -> list[KnowledgeItem]:
        items = self._ITEMS
        if categories:
            items = [i for i in items if i.category in categories]
        # Simple stub: return items filtered by keyword
        q = query.lower()
        scored = []
        for item in items:
            score = 0.0
            if q in item.title.lower():
                score += 0.5
            if q in item.content.lower():
                score += 0.3
            if score > 0 or not q:
                item.relevance_score = score or item.relevance_score
                scored.append(item)
        scored.sort(key=lambda x: x.relevance_score, reverse=True)
        return scored[:limit]

    def audit_memory(self) -> AuditReport:
        stale = [i for i in self._ITEMS if i.status == ValidationStatus.STALE]
        return AuditReport(
            stale_items=stale,
            contradicted_items=[],
            missing_evidence=[],
            recommendations=[
                "Review 'Bcrypt for password hashing' — may have changed.",
            ],
        )

    def get_status(self) -> MemoryStatus:
        current = len([i for i in self._ITEMS if i.status == ValidationStatus.CURRENT])
        stale = len([i for i in self._ITEMS if i.status == ValidationStatus.STALE])
        return MemoryStatus(
            total_items=len(self._ITEMS),
            current_items=current,
            stale_items=stale,
            contradicted_items=0,
            last_audit=datetime(2025, 1, 1, tzinfo=timezone.utc),
            db_path=":memory:",
            is_healthy=True,
        )

    def is_healthy(self) -> bool:
        return True


# ---------------------------------------------------------------------------
# Member 3 stub
# ---------------------------------------------------------------------------


class StubContextRetriever(ContextRetriever):
    """Deterministic stub for Member 3 — ContextRetriever."""

    def __init__(
        self,
        memory: ProjectMemory | None = None,
        code_intel: CodeIntelligence | None = None,
    ):
        self._memory = memory or StubProjectMemory()
        self._code_intel = code_intel or StubCodeIntelligence()

    def get_context(
        self,
        task: str,
        token_budget: int = 8000,
        include_code: bool = True,
    ) -> ProjectContext:
        knowledge = self._memory.search_knowledge(task, limit=5)
        code_chunks = self._code_intel.get_related_code(task, limit=3) if include_code else []
        warnings = self.get_relevant_warnings(task)
        summary = self._memory.get_project_summary()

        return ProjectContext(
            task=task,
            project_summary=summary,
            knowledge_items=knowledge,
            code_chunks=code_chunks,
            warnings=warnings,
            token_count=min(
                len(task.split()) * 2
                + sum(len(k.content.split()) for k in knowledge)
                + sum(len(c.content.split()) for c in code_chunks),
                token_budget,
            ),
            token_budget=token_budget,
            retrieval_notes="Stub retrieval — deterministic for testing.",
        )

    def get_relevant_warnings(self, task: str) -> list[Warning]:
        warnings = []
        task_lower = task.lower()

        # Authentication warning
        if any(kw in task_lower for kw in ["auth", "authentication", "login", "public", "remove check"]):
            warnings.append(
                Warning(
                    severity="high",
                    category="constraint",
                    message=(
                        "This task may violate SEC-07: All endpoints must require authentication. "
                        "Removing auth checks requires security team approval."
                    ),
                    constraint_id="SEC-07",
                    evidence=["security-policy-v2"],
                    suggested_action="Get explicit sign-off from the security team before proceeding.",
                )
            )

        # Architecture warning
        if any(kw in task_lower for kw in ["direct db", "database", "sql", "query"]):
            warnings.append(
                Warning(
                    severity="medium",
                    category="architecture",
                    message=(
                        "Ensure database access goes through the Repository layer. "
                        "Direct DB access from the API layer violates the layered architecture."
                    ),
                    constraint_id="ARCH-001",
                    evidence=["ARCH-001"],
                    suggested_action="Use the Repository pattern instead of direct SQLAlchemy queries.",
                )
            )

        return warnings

    def estimate_tokens(self, context: ProjectContext) -> int:
        return context.token_count
