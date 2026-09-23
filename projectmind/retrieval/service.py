"""Concrete Member 3 implementation of the ContextRetriever interface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from projectmind.core.interfaces import (
    CodeChunk,
    ContextRetriever,
    KnowledgeItem,
    ProjectContext,
    ProjectSummary as CoreProjectSummary,
    Warning as CoreWarning,
)
from projectmind.retrieval.assembly import assemble_context_package
from projectmind.retrieval.bm25 import BM25Retriever
from projectmind.retrieval.budget import score_candidates, select_within_budget
from projectmind.retrieval.contracts import CodeEntity, MemoryRecord, MemoryStatus, MemoryType
from projectmind.retrieval.token_utils import count_tokens

if TYPE_CHECKING:
    from projectmind.core.interfaces import CodeIntelligence, ProjectMemory


class RetrievalService(ContextRetriever):
    """
    Member 3 implementation of Member 4's ContextRetriever interface.

    Combines CodeIntelligence (Member 1) and ProjectMemory (Member 2) outputs
    using BM25 keyword search and utility-per-token budget control.
    """

    def __init__(
        self,
        code_intelligence: CodeIntelligence | None = None,
        project_memory: ProjectMemory | None = None,
    ) -> None:
        self.code_intelligence = code_intelligence
        self.project_memory = project_memory

    def get_context(
        self,
        task: str,
        token_budget: int = 8000,
        include_code: bool = True,
    ) -> ProjectContext:
        """
        Retrieve minimum-sufficient context for an AI agent to work on a task.
        """
        memories: list[MemoryRecord] = []
        knowledge_items: list[KnowledgeItem] = []
        if self.project_memory is not None:
            knowledge_items = self.project_memory.search_knowledge(task, limit=20)
            for item in knowledge_items:
                memories.append(
                    MemoryRecord(
                        id=item.id,
                        type=MemoryType.FACT,
                        content=f"{item.title}: {item.content}",
                        source=", ".join(item.evidence) if item.evidence else "",
                        status=MemoryStatus.ACTIVE,
                        importance=item.relevance_score or 0.5,
                        confidence=0.9,
                        freshness=1.0,
                    )
                )

        code_entities: list[CodeEntity] = []
        code_chunks: list[CodeChunk] = []
        if include_code and self.code_intelligence is not None:
            code_chunks = self.code_intelligence.get_related_code(task, limit=10)
            for chunk in code_chunks:
                code_entities.append(
                    CodeEntity(
                        id=f"{chunk.file_path}:{chunk.start_line}",
                        name=chunk.summary or chunk.file_path,
                        file=chunk.file_path,
                        kind="code_chunk",
                        snippet=chunk.content,
                        importance_score=chunk.relevance_score or 0.8,
                    )
                )

        retriever = BM25Retriever(memories, code_entities)
        candidates = retriever.search(task, top_k=20)
        budgeted = score_candidates(candidates)
        selected = select_within_budget(budgeted, token_budget)

        summary_text = "ProjectMind System"
        core_summary: CoreProjectSummary | None = None
        if self.project_memory is not None:
            try:
                core_summary = self.project_memory.get_project_summary()
                summary_text = f"{core_summary.name}: {core_summary.description}"
            except Exception:
                pass

        pkg = assemble_context_package(
            query=task,
            selected=selected,
            all_candidates=budgeted,
            token_budget=token_budget,
            project_summary=summary_text,
        )

        selected_knowledge: list[KnowledgeItem] = []
        selected_code: list[CodeChunk] = []

        for b_item in selected:
            if b_item.item_type == "memory":
                m_id = b_item.item_id
                matched = next((k for k in knowledge_items if k.id == m_id), None)
                if matched:
                    selected_knowledge.append(matched)
            elif b_item.item_type == "code":
                c_id = b_item.item_id
                matched_c = next(
                    (c for c in code_chunks if f"{c.file_path}:{c.start_line}" == c_id),
                    None,
                )
                if matched_c:
                    selected_code.append(matched_c)

        if not selected_knowledge and knowledge_items:
            selected_knowledge = knowledge_items[:5]
        if include_code and not selected_code and code_chunks:
            selected_code = code_chunks[:5]

        warnings = self.get_relevant_warnings(task)

        calc_tokens = (
            sum(count_tokens(k.content) for k in selected_knowledge)
            + sum(count_tokens(c.content) for c in selected_code)
            + count_tokens(summary_text)
        )

        return ProjectContext(
            task=task,
            project_summary=core_summary,
            knowledge_items=selected_knowledge,
            code_chunks=selected_code,
            warnings=warnings,
            token_count=calc_tokens,
            token_budget=token_budget,
            retrieval_notes=f"Retrieved {len(selected_knowledge)} knowledge items and {len(selected_code)} code chunks (considered {pkg.items_considered} items).",
        )

    def get_relevant_warnings(self, task: str) -> list[CoreWarning]:
        """Return warnings that may affect the given task."""
        warnings: list[CoreWarning] = []
        task_lower = task.lower()

        if any(
            term in task_lower for term in ["auth", "login", "password", "token", "secret", "oauth"]
        ):
            warnings.append(
                CoreWarning(
                    severity="high",
                    category="security",
                    message="Task touches authentication/security components. Ensure credentials and tokens are not logged or exposed.",
                    constraint_id="SEC-01",
                    suggested_action="Verify secure auth patterns and environment variables.",
                )
            )

        if any(term in task_lower for term in ["db", "database", "sqlite", "query", "sql"]):
            warnings.append(
                CoreWarning(
                    severity="medium",
                    category="architecture",
                    message="Database operations detected. Use parameterization to prevent injection vulnerabilities.",
                    constraint_id="ARCH-02",
                    suggested_action="Review database queries in repository transactions.",
                )
            )

        return warnings

    def estimate_tokens(self, context: ProjectContext) -> int:
        """Estimate the token count for the given context package."""
        total = 0
        if context.project_summary:
            total += count_tokens(context.project_summary.description)
        for k in context.knowledge_items:
            total += count_tokens(k.content)
        for c in context.code_chunks:
            total += count_tokens(c.content)
        return total
