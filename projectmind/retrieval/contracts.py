"""Data contracts for ProjectMind retrieval and context optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MemoryType(Enum):
    GOAL = "goal"
    ARCHITECTURE = "architecture"
    DECISION = "decision"
    CONSTRAINT = "constraint"
    HISTORY = "history"
    REQUIREMENT = "requirement"
    NON_GOAL = "non_goal"
    FACT = "fact"
    RATIONALE = "rationale"
    ISSUE = "issue"
    RELATIONSHIP = "relationship"


class MemoryStatus(Enum):
    ACTIVE = "active"
    STALE = "stale"
    HISTORICAL = "historical"
    CONTRADICTED = "contradicted"


@dataclass
class MemoryRecord:
    id: str
    type: MemoryType
    content: str
    source: str = ""
    status: MemoryStatus = MemoryStatus.ACTIVE
    importance: float = 0.5
    confidence: float = 0.5
    freshness: float = 1.0


@dataclass
class CodeEntity:
    id: str
    name: str
    file: str
    kind: str = "symbol"
    snippet: str | None = None
    importance_score: float = 0.5


@dataclass
class RetrievalResult:
    item_id: str
    item_type: str  # "memory" | "code"
    score: float
    bm25_score: float
    matched_item: Any


@dataclass
class ContextPackage:
    project_summary: str
    relevant_facts: list[dict[str, Any]] = field(default_factory=list)
    relevant_code: list[dict[str, Any]] = field(default_factory=list)
    recent_changes: list[dict[str, Any]] = field(default_factory=list)
    known_issues: list[dict[str, Any]] = field(default_factory=list)
    total_tokens: int = 0
    token_budget: int = 8000
    items_considered: int = 0
    items_included: int = 0
