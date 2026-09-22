from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EvidenceKind(str, Enum):
    """
    Identifies the type of project artifact that provides evidence
    for a memory.

    CODE:
        Evidence comes from a source-code file.

    DOCUMENT:
        Evidence comes from project documentation such as README,
        design documents, or specifications.

    COMMIT:
        Evidence is associated with a Git commit.

    TEST:
        Evidence comes from an automated test.

    CONFIGURATION:
        Evidence comes from a configuration file or configuration
        artifact.
    """

    CODE = "CODE"
    DOCUMENT = "DOCUMENT"
    COMMIT = "COMMIT"
    TEST = "TEST"
    CONFIGURATION = "CONFIGURATION"


class Evidence(BaseModel):
    """
    Represents a traceable source of evidence supporting a project
    memory.

    An Evidence record identifies where a piece of project knowledge
    came from and allows ProjectMind to trace a memory back to the
    corresponding project artifact.

    Example:

        Memory:
            "ProjectMind uses SQLite for persistent project memory."

        Evidence:
            file_path = "memory/repository.py"
            symbol = "MemoryRepository"
            commit = "a81f23c"
            line_start = 15
            line_end = 32

    The Memory model stores the evidence identifier, while this model
    stores the actual provenance information.
    """

    # ============================================================
    # PYDANTIC CONFIGURATION
    # ============================================================

    model_config = ConfigDict(
        validate_assignment=True,
        extra="forbid",
    )

    # ============================================================
    # IDENTITY
    # ============================================================

    # Unique identifier for this evidence record.
    #
    # Example:
    #     E001
    id: str = Field(
        min_length=1,
        description="Unique identifier for the evidence record.",
    )

    # ============================================================
    # EVIDENCE TYPE
    # ============================================================

    # Type of artifact providing the evidence.
    kind: EvidenceKind

    # ============================================================
    # SOURCE FILE
    # ============================================================

    # Repository-relative path of the file containing the evidence.
    #
    # Examples:
    #     memory/repository.py
    #     README.md
    #     config/database.py
    #
    # This is optional because some evidence can be associated with
    # a Git commit without referring to one particular file.
    file_path: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Repository-relative path of the evidence source.",
    )

    # ============================================================
    # CODE SYMBOL
    # ============================================================

    # Optional class, function, method, or other code symbol
    # associated with the evidence.
    #
    # Examples:
    #     MemoryRepository
    #     create_memory
    #     update_memory
    #
    # This is normally useful for CODE and TEST evidence.
    symbol: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Optional class, function, or code symbol.",
    )

    # ============================================================
    # GIT VERSION
    # ============================================================

    # Git commit at which the evidence was observed.
    #
    # Example:
    #     a81f23c
    #
    # Keeping the commit allows ProjectMind to determine which
    # version of the repository supported the memory.
    commit: Optional[str] = Field(
        default=None,
        min_length=1,
        description="Git commit associated with the evidence.",
    )

    # ============================================================
    # SOURCE LOCATION
    # ============================================================

    # First line containing the relevant evidence.
    #
    # Example:
    #     15
    #
    # Line numbers are optional because not every evidence source
    # has a line-based location.
    line_start: Optional[int] = Field(
        default=None,
        ge=1,
        description="Starting line number of the evidence.",
    )

    # Last line containing the relevant evidence.
    #
    # Example:
    #     32
    line_end: Optional[int] = Field(
        default=None,
        ge=1,
        description="Ending line number of the evidence.",
    )

    # ============================================================
    # DESCRIPTION
    # ============================================================

    # Human-readable explanation of what the evidence demonstrates
    # and why it supports the associated memory.
    #
    # Example:
    #     "SQLite connection and memory persistence implementation."
    description: str = Field(
        min_length=1,
        description="Explanation of why this evidence supports the memory.",
    )

    # ============================================================
    # VALIDATION
    # ============================================================

    @model_validator(mode="after")
    def validate_source_location(self) -> "Evidence":
        """
        Validate the relationship between line_start and line_end.

        If both values are provided, the ending line cannot occur
        before the starting line.

        Valid:
            line_start=15
            line_end=32

        Invalid:
            line_start=32
            line_end=15
        """

        if (
            self.line_start is not None
            and self.line_end is not None
            and self.line_end < self.line_start
        ):
            raise ValueError(
                "line_end must be greater than or equal to line_start."
            )

        return self