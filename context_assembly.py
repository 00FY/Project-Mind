"""
Phase 6/7 — Context Assembly & Compression.

Takes the budget-selected items and assembles them into the standard
ContextPackage contract: project summary, relevant facts, relevant code,
recent changes, known issues — the shape every other member's tooling
(and eventually the MCP layer) can rely on.
"""

from __future__ import annotations

from .budget_controller import BudgetedItem
from .contracts import CodeEntity, ContextPackage, MemoryRecord, MemoryType
from .token_utils import count_tokens


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
            code.append({"name": c.name, "file": c.file, "snippet": c.snippet})
        else:
            m: MemoryRecord = item.matched_item  # type: ignore[assignment]
            entry = {"content": m.content, "source": m.source, "status": m.status.value}
            if m.type == MemoryType.ISSUE:
                issues.append(entry)
            else:
                facts.append(entry)

    total_tokens = sum(i.tokens for i in selected) + count_tokens(project_summary)

    return ContextPackage(
        project_summary=project_summary,
        relevant_facts=facts,
        relevant_code=code,
        recent_changes=[],  # populated once Member 1's change-event feed exists
        known_issues=issues,
        total_tokens=total_tokens,
        token_budget=token_budget,
        items_considered=len(all_candidates),
        items_included=len(selected),
    )
