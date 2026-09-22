from datetime import datetime, timezone
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from .enums import MemoryStatus, MemoryType, MemoryOrigin


def utc_now() -> datetime:
    """
    Return the current time as a timezone-aware UTC datetime.

    All ProjectMind runtime timestamps should use UTC-aware
    datetime objects to avoid naive/aware datetime mismatches.
    """

    return datetime.now(timezone.utc)


class Memory(BaseModel):
    """
    Represents a single piece of persistent project knowledge.

    A memory can represent:
    - a fact
    - architectural information
    - a technical decision
    - a rationale
    - a requirement
    - a constraint
    - an issue
    - a relationship
    - historical information
    - a project goal
    - a project non-goal

    The memory also contains temporal information so that
    ProjectMind can determine whether a fact is currently valid,
    historically valid, stale, or contradicted.
    """

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
    )

    # ============================================================
    # IDENTITY
    # ============================================================

    id: str

    type: MemoryType

    content: str

    # ============================================================
    # STRUCTURED FACT IDENTITY
    # ============================================================

    subject: Optional[str] = None

    value: Optional[str] = None

    origin: Optional[MemoryOrigin] = None

    # ============================================================
    # IMPORTANCE AND CONFIDENCE
    # ============================================================

    importance: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
    )

    # ============================================================
    # MEMORY LIFECYCLE
    # ============================================================

    status: MemoryStatus = MemoryStatus.ACTIVE

    # ============================================================
    # RECORD TIMESTAMPS
    # ============================================================

    created_at: datetime

    updated_at: datetime

    invalidated_at: Optional[datetime] = None

    # ============================================================
    # EVIDENCE VERIFICATION
    # ============================================================

    last_verified_at: Optional[datetime] = None

    # ============================================================
    # GIT / VERSION INFORMATION
    # ============================================================

    observed_at_commit: Optional[str] = None

    # ============================================================
    # TEMPORAL MEMORY
    # ============================================================

    valid_from: Optional[datetime] = None

    valid_until: Optional[datetime] = None

    # ============================================================
    # EVIDENCE
    # ============================================================

    evidence: list[str] = Field(
        default_factory=list
    )

    # ============================================================
    # RELATED ENTITIES
    # ============================================================

    related_entities: list[str] = Field(
        default_factory=list
    )

    # ============================================================
    # VALIDATION
    # ============================================================

    @model_validator(mode="after")
    def validate_datetimes(self) -> "Memory":
        """
        Ensure all supplied datetimes are timezone-aware and that
        the temporal validity interval is logically ordered.
        """

        datetime_fields = {
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_verified_at": self.last_verified_at,
            "valid_from": self.valid_from,
            "valid_until": self.valid_until,
            "invalidated_at": self.invalidated_at,
        }

        for field_name, value in datetime_fields.items():
            if value is None:
                continue

            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(
                    f"{field_name} must be timezone-aware."
                )

        if (
            self.valid_from is not None
            and self.valid_until is not None
            and self.valid_from > self.valid_until
        ):
            raise ValueError(
                "valid_from cannot be later than valid_until."
            )

        if self.importance >= 0.7 and not self.evidence:
            raise ValueError(
                "Important memories must have at least one evidence reference."
            )

        return self