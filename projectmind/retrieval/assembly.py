"""
Phase 6/7 — Context Assembly & Compression.

Takes budget-selected items and assembles them into ContextPackage.
"""

from __future__ import annotations

from projectmind.retrieval.budget import BudgetedItem
from projectmind.retrieval.contracts import CodeEntity, ContextPackage, MemoryRecord, MemoryType
from projectmind.retrieval.token_utils import count_tokens


def assemble_context_package(
    query: str,
    selected: list[BudgetedItem],
    all_candidates: list[BudgetedItem],
    token_budget: int,
    project_summary: str = "ProjectMind demo project.",
) -> ContextPackage:
    facts, code, issues = [], [], []

    for item in selected:
        if item.item_type == "code":
            c: CodeEntity = item.matched_item  # type: ignore[assignment]
            code.append(
                {
                    "name": getattr(c, "name", str(c)),
                    "file": getattr(c, "file", ""),
                    "snippet": getattr(c, "snippet", None),
                }
            )
        else:
            m: MemoryRecord = item.matched_item  # type: ignore[assignment]
            m_type = getattr(m, "type", MemoryType.FACT)
            m_status = getattr(m, "status", "active")
            status_str = m_status.value if hasattr(m_status, "value") else str(m_status)
            entry = {
                "content": getattr(m, "content", str(m)),
                "source": getattr(m, "source", ""),
                "status": status_str,
            }
            if m_type == MemoryType.ISSUE or (hasattr(m_type, "value") and m_type.value == "issue"):
                issues.append(entry)
            else:
                facts.append(entry)

    total_tokens = sum(i.tokens for i in selected) + count_tokens(project_summary)

    return ContextPackage(
        project_summary=project_summary,
        relevant_facts=facts,
        relevant_code=code,
        recent_changes=[],
        known_issues=issues,
        total_tokens=total_tokens,
        token_budget=token_budget,
        items_considered=len(all_candidates),
        items_included=len(selected),
    )
