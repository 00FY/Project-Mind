from enum import Enum


class MemoryType(str, Enum):
    """
    Defines the type/category of project knowledge stored in memory.
    """

    FACT = "FACT"
    ARCHITECTURE = "ARCHITECTURE"
    DECISION = "DECISION"
    RATIONALE = "RATIONALE"
    REQUIREMENT = "REQUIREMENT"
    CONSTRAINT = "CONSTRAINT"
    ISSUE = "ISSUE"
    RELATIONSHIP = "RELATIONSHIP"
    HISTORY = "HISTORY"
    GOAL = "GOAL"
    NON_GOAL = "NON_GOAL"


class MemoryStatus(str, Enum):
    """
    Defines the current lifecycle state of a memory.
    """

    ACTIVE = "ACTIVE"
    HISTORICAL = "HISTORICAL"
    STALE = "STALE"
    CONTRADICTED = "CONTRADICTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class MemoryOrigin(str, Enum):
    """
    Defines how a memory was produced.
    """

    DETERMINISTIC = "DETERMINISTIC"
    LLM = "LLM"
    USER = "USER"
