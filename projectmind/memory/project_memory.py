from __future__ import annotations

from datetime import datetime, timezone

from projectmind.core.interfaces import (
    AuditReport,
    KnowledgeItem,
    MemoryStatus as CoreMemoryStatus,
    ProjectMemory,
    ProjectSummary,
    ValidationStatus,
)

from .enums import MemoryStatus, MemoryType
from .repository import MemoryRepository


class SQLiteProjectMemory(ProjectMemory):
    """
    Member 2 implementation of Member 4's ProjectMemory interface.

    Exposes the persistent SQLite memory engine through the shared
    ProjectMind core contract.
    """

    _STATUS_MAP = {
        MemoryStatus.ACTIVE: ValidationStatus.CURRENT,
        MemoryStatus.STALE: ValidationStatus.STALE,
        MemoryStatus.HISTORICAL: ValidationStatus.HISTORICAL,
        MemoryStatus.CONTRADICTED: ValidationStatus.CONTRADICTED,
        MemoryStatus.NEEDS_REVIEW: ValidationStatus.STALE,
    }

    _CATEGORY_MAP = {
        MemoryType.GOAL: "goal",
        MemoryType.ARCHITECTURE: "architecture",
        MemoryType.DECISION: "decision",
        MemoryType.CONSTRAINT: "constraint",
        MemoryType.HISTORY: "history",
        MemoryType.REQUIREMENT: "constraint",
        MemoryType.NON_GOAL: "constraint",
        MemoryType.FACT: "history",
        MemoryType.RATIONALE: "decision",
        MemoryType.ISSUE: "history",
        MemoryType.RELATIONSHIP: "history",
    }

    def __init__(self, repository: MemoryRepository) -> None:
        self.repository = repository

    def _to_knowledge_item(self, memory) -> KnowledgeItem:
        return KnowledgeItem(
            id=memory.id,
            category=self._CATEGORY_MAP[memory.type],
            title=self._build_title(memory),
            content=memory.content,
            status=self._STATUS_MAP[memory.status],
            evidence=list(memory.evidence),
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            relevance_score=memory.importance,
        )

    @staticmethod
    def _build_title(memory) -> str:
        if memory.subject:
            return memory.subject

        words = memory.content.strip().split()

        if not words:
            return memory.type.value

        title = " ".join(words[:10])

        if len(words) > 10:
            title += "..."

        return title

    def get_project_summary(self) -> ProjectSummary:
        memories = self.repository.list_memories()

        goals = [
            memory.content
            for memory in memories
            if memory.type == MemoryType.GOAL and memory.status == MemoryStatus.ACTIVE
        ]

        key_decisions = [
            memory.content
            for memory in memories
            if memory.type == MemoryType.DECISION and memory.status == MemoryStatus.ACTIVE
        ]

        active_constraints = [
            memory.content
            for memory in memories
            if memory.type == MemoryType.CONSTRAINT and memory.status == MemoryStatus.ACTIVE
        ]

        return ProjectSummary(
            name="ProjectMind",
            description="Persistent project knowledge and memory system.",
            goals=goals,
            tech_stack=[],
            key_decisions=key_decisions,
            active_constraints=active_constraints,
            last_updated=self._latest_update(memories),
        )

    @staticmethod
    def _latest_update(memories) -> datetime:
        if not memories:
            return datetime.now(timezone.utc)

        return max(memory.updated_at for memory in memories)

    def search_knowledge(
        self,
        query: str,
        limit: int = 10,
        categories: list[str] | None = None,
    ) -> list[KnowledgeItem]:

        query_terms = [term.lower() for term in query.split() if term.strip()]

        memories = self.repository.list_memories()

        if categories:
            allowed_types = {
                memory_type
                for memory_type, category in self._CATEGORY_MAP.items()
                if category in categories
            }

            memories = [memory for memory in memories if memory.type in allowed_types]

        scored: list[tuple[float, object]] = []

        for memory in memories:
            searchable = " ".join(
                filter(
                    None,
                    [
                        memory.content,
                        memory.subject,
                        memory.value,
                        memory.type.value,
                    ],
                )
            ).lower()

            if not query_terms:
                score = memory.importance
            else:
                matched = sum(1 for term in query_terms if term in searchable)

                if matched == 0:
                    continue

                score = matched / len(query_terms)

                # Importance is used as a deterministic tie-breaker.
                score += memory.importance * 0.01

            scored.append((score, memory))

        scored.sort(
            key=lambda item: (
                item[0],
                item[1].updated_at,
            ),
            reverse=True,
        )

        return [self._to_knowledge_item(memory) for _, memory in scored[:limit]]

    def audit_memory(self) -> AuditReport:
        memories = self.repository.list_memories()

        stale_items = [
            self._to_knowledge_item(memory)
            for memory in memories
            if memory.status
            in {
                MemoryStatus.STALE,
                MemoryStatus.NEEDS_REVIEW,
            }
        ]

        contradicted_items = [
            self._to_knowledge_item(memory)
            for memory in memories
            if memory.status == MemoryStatus.CONTRADICTED
        ]

        missing_evidence = [
            self._to_knowledge_item(memory) for memory in memories if not memory.evidence
        ]

        recommendations: list[str] = []

        if stale_items:
            recommendations.append("Review stale or review-required project memories.")

        if contradicted_items:
            recommendations.append("Resolve contradicted project memories.")

        if missing_evidence:
            recommendations.append("Add evidence references to unsupported memories.")

        return AuditReport(
            stale_items=stale_items,
            contradicted_items=contradicted_items,
            missing_evidence=missing_evidence,
            recommendations=recommendations,
            timestamp=datetime.now(timezone.utc),
        )

    def get_status(self) -> CoreMemoryStatus:
        memories = self.repository.list_memories()

        current_items = sum(memory.status == MemoryStatus.ACTIVE for memory in memories)

        stale_items = sum(
            memory.status
            in {
                MemoryStatus.STALE,
                MemoryStatus.NEEDS_REVIEW,
            }
            for memory in memories
        )

        contradicted_items = sum(memory.status == MemoryStatus.CONTRADICTED for memory in memories)

        healthy = True
        error_message = ""

        try:
            self.repository.list_memories()
        except Exception as exc:
            healthy = False
            error_message = str(exc)

        return CoreMemoryStatus(
            total_items=len(memories),
            current_items=current_items,
            stale_items=stale_items,
            contradicted_items=contradicted_items,
            last_audit=datetime.now(timezone.utc),
            db_path=str(self.repository.db_path),
            is_healthy=healthy,
            error_message=error_message,
        )

    def is_healthy(self) -> bool:
        try:
            self.repository.list_memories()
            return True
        except Exception:
            return False
