"""
Core interfaces for ProjectMind.

These abstract base classes define the contracts between Member 4
(Platform & Agent Integration) and Members 1, 2, and 3.

Members 1, 2, and 3 MUST implement these interfaces.
Member 4 calls them through these interfaces exclusively.

Usage:
    from projectmind.core.interfaces import CodeIntelligence, ProjectMemory, ContextRetriever
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

# ---------------------------------------------------------------------------
# Shared data models
# ---------------------------------------------------------------------------


class ValidationStatus(StrEnum):
    """Validity status of a knowledge item."""

    CURRENT = "current"
    STALE = "stale"
    HISTORICAL = "historical"
    CONTRADICTED = "contradicted"


class HealthStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CodeChunk:
    """A fragment of source code relevant to a query."""

    file_path: str
    start_line: int
    end_line: int
    content: str
    language: str = "python"
    relevance_score: float = 0.0
    summary: str = ""


@dataclass
class FileSummary:
    """High-level summary of a single source file."""

    path: str
    language: str
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    summary: str = ""
    last_modified: datetime | None = None


@dataclass
class GitChange:
    """A git change affecting one file."""

    file_path: str
    change_type: str  # "added" | "modified" | "deleted" | "renamed"
    additions: int = 0
    deletions: int = 0
    diff_summary: str = ""
    commit_hash: str = ""
    commit_message: str = ""
    timestamp: datetime | None = None


@dataclass
class IndexResult:
    """Result of indexing a project directory."""

    files_indexed: int
    files_skipped: int
    duration_seconds: float
    errors: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class KnowledgeItem:
    """A single item retrieved from project memory."""

    id: str
    category: str  # "goal" | "architecture" | "decision" | "constraint" | "history"
    title: str
    content: str
    status: ValidationStatus = ValidationStatus.CURRENT
    evidence: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    relevance_score: float = 0.0


@dataclass
class ProjectSummary:
    """High-level summary of the project from memory."""

    name: str
    description: str
    goals: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    key_decisions: list[str] = field(default_factory=list)
    active_constraints: list[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MemoryStatus:
    """Current status of the project memory engine."""

    total_items: int
    current_items: int
    stale_items: int
    contradicted_items: int
    last_audit: datetime | None = None
    db_path: str = ""
    is_healthy: bool = True
    error_message: str = ""


@dataclass
class AuditReport:
    """Result of a memory audit."""

    stale_items: list[KnowledgeItem] = field(default_factory=list)
    contradicted_items: list[KnowledgeItem] = field(default_factory=list)
    missing_evidence: list[KnowledgeItem] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class Warning:
    """A warning about a task that may violate a constraint or decision."""

    severity: str  # "low" | "medium" | "high" | "critical"
    category: str  # "constraint" | "decision" | "architecture" | "security"
    message: str
    constraint_id: str = ""
    evidence: list[str] = field(default_factory=list)
    suggested_action: str = ""


@dataclass
class ProjectContext:
    """
    The minimum-sufficient context for an AI agent to work on a task.
    Produced by Member 3; consumed by the MCP server.
    """

    task: str
    project_summary: ProjectSummary | None = None
    knowledge_items: list[KnowledgeItem] = field(default_factory=list)
    code_chunks: list[CodeChunk] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
    token_count: int = 0
    token_budget: int = 8000
    retrieval_notes: str = ""


# ---------------------------------------------------------------------------
# Member 1 — Code Intelligence interface
# ---------------------------------------------------------------------------


class CodeIntelligence(abc.ABC):
    """
    Abstract interface for Member 1 — Code Intelligence.

    Understands the repository: files, functions, classes, relationships,
    git changes, and evidence.
    """

    @abc.abstractmethod
    def index_project(self, project_root: str) -> IndexResult:
        """
        Parse and index all source files in the project.

        Args:
            project_root: Absolute path to the project directory.

        Returns:
            IndexResult with stats about what was indexed.
        """
        ...

    @abc.abstractmethod
    def get_file_summary(self, file_path: str) -> FileSummary:
        """
        Return a summary of a single source file.

        Args:
            file_path: Absolute or repo-relative path to the file.
        """
        ...

    @abc.abstractmethod
    def get_related_code(self, query: str, limit: int = 5) -> list[CodeChunk]:
        """
        Retrieve code chunks most relevant to the given query.

        Args:
            query: Natural language or code snippet to match against.
            limit: Maximum number of chunks to return.
        """
        ...

    @abc.abstractmethod
    def get_git_changes(self, since_commit: str = "HEAD~1") -> list[GitChange]:
        """
        Return recent git changes since the specified commit reference.

        Args:
            since_commit: Git ref (commit hash, branch, tag) to compare from.
        """
        ...

    @abc.abstractmethod
    def get_last_indexed(self) -> datetime | None:
        """Return the timestamp of the most recent successful index, or None."""
        ...


# ---------------------------------------------------------------------------
# Member 2 — Project Memory interface
# ---------------------------------------------------------------------------


class ProjectMemory(abc.ABC):
    """
    Abstract interface for Member 2 — Project Memory.

    Stores and retrieves project goals, architecture decisions, constraints,
    history, and evidence. Tracks whether knowledge is current/stale/contradicted.
    """

    @abc.abstractmethod
    def get_project_summary(self) -> ProjectSummary:
        """Return the high-level project summary."""
        ...

    @abc.abstractmethod
    def search_knowledge(
        self,
        query: str,
        limit: int = 10,
        categories: list[str] | None = None,
    ) -> list[KnowledgeItem]:
        """
        Semantic search over the project's knowledge base.

        Args:
            query: Natural language query.
            limit: Maximum number of items to return.
            categories: Optional filter by category (goal, decision, constraint, etc.)
        """
        ...

    @abc.abstractmethod
    def audit_memory(self) -> AuditReport:
        """
        Audit the knowledge base for stale, contradicted, or unsupported items.

        Returns an AuditReport with findings and recommendations.
        """
        ...

    @abc.abstractmethod
    def get_status(self) -> MemoryStatus:
        """Return current health and stats of the memory store."""
        ...

    @abc.abstractmethod
    def is_healthy(self) -> bool:
        """Quick boolean health check — True if memory store is accessible."""
        ...


# ---------------------------------------------------------------------------
# Member 3 — Context & Retrieval interface
# ---------------------------------------------------------------------------


class ContextRetriever(abc.ABC):
    """
    Abstract interface for Member 3 — Context & Retrieval.

    Decides what the AI agent needs for a specific task: relevant knowledge,
    relevant code, warnings, and a token-budgeted context package.
    """

    @abc.abstractmethod
    def get_context(
        self,
        task: str,
        token_budget: int = 8000,
        include_code: bool = True,
    ) -> ProjectContext:
        """
        Retrieve the minimum-sufficient context for an AI agent to work on a task.

        Args:
            task: The task description from the AI agent or user.
            token_budget: Maximum tokens to include in the context.
            include_code: Whether to include code chunks in the context.

        Returns:
            ProjectContext with all relevant information within the budget.
        """
        ...

    @abc.abstractmethod
    def get_relevant_warnings(self, task: str) -> list[Warning]:
        """
        Return warnings that may affect the given task.

        For example, if the task involves authentication, this might return
        a warning about constraint SEC-07.

        Args:
            task: The task description.
        """
        ...

    @abc.abstractmethod
    def estimate_tokens(self, context: ProjectContext) -> int:
        """Estimate the token count for the given context package."""
        ...


# ---------------------------------------------------------------------------
# Registry — allows runtime injection of concrete implementations
# ---------------------------------------------------------------------------


class ProjectMindCore:
    """
    Central registry that holds the concrete implementations of all three
    member interfaces. Member 4 uses this to access the full system.

    Usage:
        core = ProjectMindCore(
            code_intelligence=MyCodeIntelligence(),
            project_memory=MyProjectMemory(),
            context_retriever=MyContextRetriever(),
        )
    """

    def __init__(
        self,
        code_intelligence: CodeIntelligence | None = None,
        project_memory: ProjectMemory | None = None,
        context_retriever: ContextRetriever | None = None,
    ):
        self._code_intelligence = code_intelligence
        self._project_memory = project_memory
        self._context_retriever = context_retriever

    @property
    def code_intelligence(self) -> CodeIntelligence:
        if self._code_intelligence is None:
            raise RuntimeError(
                "CodeIntelligence (Member 1) is not registered. "
                "Run 'projectmind doctor' to diagnose."
            )
        return self._code_intelligence

    @property
    def project_memory(self) -> ProjectMemory:
        if self._project_memory is None:
            raise RuntimeError(
                "ProjectMemory (Member 2) is not registered. Run 'projectmind doctor' to diagnose."
            )
        return self._project_memory

    @property
    def context_retriever(self) -> ContextRetriever:
        if self._context_retriever is None:
            raise RuntimeError(
                "ContextRetriever (Member 3) is not registered. "
                "Run 'projectmind doctor' to diagnose."
            )
        return self._context_retriever

    def is_fully_configured(self) -> bool:
        return all(
            [
                self._code_intelligence is not None,
                self._project_memory is not None,
                self._context_retriever is not None,
            ]
        )

    def available_modules(self) -> dict[str, bool]:
        return {
            "code_intelligence": self._code_intelligence is not None,
            "project_memory": self._project_memory is not None,
            "context_retriever": self._context_retriever is not None,
        }


# Global core instance — populated at startup via dependency injection
_core: ProjectMindCore | None = None


def get_core() -> ProjectMindCore:
    """Return the global ProjectMindCore instance."""
    global _core
    if _core is None:
        _core = ProjectMindCore()
    return _core


def set_core(core: ProjectMindCore) -> None:
    """Register the global ProjectMindCore instance (called at startup)."""
    global _core
    _core = core
