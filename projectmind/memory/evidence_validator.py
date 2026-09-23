from dataclasses import dataclass, field

from .enums import MemoryType
from .models import Memory
from .repository import MemoryRepository


@dataclass
class EvidenceValidationResult:
    """
    Represents the result of validating the evidence
    associated with a memory.
    """

    valid: bool
    missing_evidence: list[str] = field(default_factory=list)
    messages: list[str] = field(default_factory=list)


class EvidenceValidator:
    """
    Validates the relationship between a memory and its
    referenced evidence records.
    """

    REQUIRED_EVIDENCE_TYPES = {
        MemoryType.DECISION,
        MemoryType.ARCHITECTURE,
        MemoryType.CONSTRAINT,
        MemoryType.REQUIREMENT,
    }

    def __init__(self, repository: MemoryRepository):
        self.repository = repository

    def validate_memory(
        self,
        memory: Memory,
    ) -> EvidenceValidationResult:
        """
        Validate the evidence associated with a memory.

        A memory is invalid when:
        1. It is important (importance >= 0.7) but has no evidence.
        2. It is a DECISION, ARCHITECTURE, CONSTRAINT, or REQUIREMENT
           but has no evidence.
        3. It references evidence records that do not exist.
        """

        missing_evidence: list[str] = []
        messages: list[str] = []

        # ========================================================
        # IMPORTANT MEMORY EVIDENCE RULE
        # ========================================================

        requires_evidence = memory.importance >= 0.7 or memory.type in self.REQUIRED_EVIDENCE_TYPES

        if requires_evidence and not memory.evidence:
            messages.append(
                f"Memory {memory.id} requires evidence because "
                f"it is important or represents a critical project "
                f"knowledge type."
            )

        # ========================================================
        # EXISTING EVIDENCE REFERENCE VALIDATION
        # ========================================================

        for evidence_id in memory.evidence:
            try:
                self.repository.get_evidence(evidence_id)

            except KeyError:
                missing_evidence.append(evidence_id)
                messages.append(f"Memory {memory.id} references missing evidence {evidence_id}.")

        # ========================================================
        # FINAL VALIDITY
        # ========================================================

        is_valid = len(missing_evidence) == 0 and not (requires_evidence and not memory.evidence)

        return EvidenceValidationResult(
            valid=is_valid,
            missing_evidence=missing_evidence,
            messages=messages,
        )
