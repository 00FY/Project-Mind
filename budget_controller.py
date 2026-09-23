"""
Phase 8 — Budget Controller.

"This is the core optimization feature." Given a set of scored candidates
and a token budget, select the highest-utility combination that fits.

utility = relevance x importance x confidence x freshness

This is a 0/1-knapsack-style selection: maximize total utility subject to
total_tokens <= budget. We use a greedy utility-per-token approximation
(fast, good enough at this scale) rather than exact DP, since candidate
counts here are small and greedy-by-density is the standard practical
approach for this kind of context-selection problem.
"""

from __future__ import annotations

from dataclasses import dataclass

from .contracts import CodeEntity, MemoryRecord, RetrievalResult
from .token_utils import count_tokens


@dataclass
class BudgetedItem:
    item_id: str
    item_type: str
    utility: float
    tokens: int
    matched_item: object


def _content_text(item_type: str, item: object) -> str:
    if item_type == "memory":
        m: MemoryRecord = item  # type: ignore[assignment]
        return m.content
    c: CodeEntity = item  # type: ignore[assignment]
    return c.snippet or c.name


def _importance_confidence_freshness(item_type: str, item: object) -> tuple[float, float, float]:
    if item_type == "memory":
        m: MemoryRecord = item  # type: ignore[assignment]
        return m.importance, m.confidence, m.freshness
    c: CodeEntity = item  # type: ignore[assignment]
    # Code entities don't carry confidence/freshness from Member 1;
    # treat as fully confident and fresh, weighted by importance_score.
    return c.importance_score, 1.0, 1.0


def score_candidates(results: list[RetrievalResult]) -> list[BudgetedItem]:
    """Convert raw retrieval results into utility-scored, token-costed items."""
    items: list[BudgetedItem] = []
    for r in results:
        importance, confidence, freshness = _importance_confidence_freshness(
            r.item_type, r.matched_item
        )
        # normalize the BM25/relevance score into a rough 0..1 band so it
        # doesn't dominate the other 0..1 factors
        relevance = min(1.0, r.score / 10.0) if r.score > 0 else 0.0
        utility = relevance * importance * confidence * freshness
        text = _content_text(r.item_type, r.matched_item)
        items.append(
            BudgetedItem(
                item_id=r.item_id,
                item_type=r.item_type,
                utility=utility,
                tokens=count_tokens(text),
                matched_item=r.matched_item,
            )
        )
    return items


def select_within_budget(items: list[BudgetedItem], token_budget: int) -> list[BudgetedItem]:
    """
    Greedy selection by utility-per-token density, respecting the budget.
    Ties broken by raw utility (prefer higher-value items when density is equal).
    """
    ranked = sorted(
        items,
        key=lambda it: (it.utility / max(it.tokens, 1), it.utility),
        reverse=True,
    )

    selected: list[BudgetedItem] = []
    remaining = token_budget
    for it in ranked:
        if it.tokens <= remaining:
            selected.append(it)
            remaining -= it.tokens
    return selected
