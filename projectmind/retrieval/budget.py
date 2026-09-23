"""
Phase 8 — Budget Controller.

Greedy utility-per-token density selection within a token budget.
"""

from __future__ import annotations

from dataclasses import dataclass

from projectmind.retrieval.contracts import CodeEntity, MemoryRecord, RetrievalResult
from projectmind.retrieval.token_utils import count_tokens


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
        return getattr(m, "content", str(m))
    c: CodeEntity = item  # type: ignore[assignment]
    res = getattr(c, "snippet", None) or getattr(c, "name", str(c))
    return str(res)


def _importance_confidence_freshness(item_type: str, item: object) -> tuple[float, float, float]:
    if item_type == "memory":
        m: MemoryRecord = item  # type: ignore[assignment]
        imp = getattr(m, "importance", getattr(m, "relevance_score", 0.5))
        conf = getattr(m, "confidence", 0.5)
        fresh = getattr(m, "freshness", 1.0)
        return imp, conf, fresh
    c: CodeEntity = item  # type: ignore[assignment]
    imp = getattr(c, "importance_score", 0.5)
    return imp, 1.0, 1.0


def score_candidates(results: list[RetrievalResult]) -> list[BudgetedItem]:
    """Convert raw retrieval results into utility-scored, token-costed items."""
    items: list[BudgetedItem] = []
    for r in results:
        importance, confidence, freshness = _importance_confidence_freshness(
            r.item_type, r.matched_item
        )
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
