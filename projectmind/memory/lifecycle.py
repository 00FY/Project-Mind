from dataclasses import dataclass
from datetime import datetime
from .models import utc_now

from .enums import MemoryStatus
from .models import Memory


class LifecycleTransitionError(ValueError):
    """
    Raised when a memory lifecycle transition is not allowed.
    """


@dataclass(frozen=True)
class LifecycleTransition:
    """
    Describes a lifecycle state transition.
    """

    memory_id: str
    old_status: MemoryStatus
    new_status: MemoryStatus
    reason: str
    changed_at: datetime


class MemoryLifecycleEngine:
    """
    Controls lifecycle transitions for project memories.

    The lifecycle engine is responsible only for state transitions.
    It does not perform stale detection, contradiction detection,
    or persistence.
    """

    ALLOWED_TRANSITIONS: dict[
        MemoryStatus,
        set[MemoryStatus],
    ] = {
        MemoryStatus.ACTIVE: {
            MemoryStatus.HISTORICAL,
            MemoryStatus.STALE,
            MemoryStatus.CONTRADICTED,
            MemoryStatus.NEEDS_REVIEW,
        },
        MemoryStatus.STALE: {
            MemoryStatus.ACTIVE,
            MemoryStatus.HISTORICAL,
            MemoryStatus.NEEDS_REVIEW,
        },
        MemoryStatus.CONTRADICTED: {
            MemoryStatus.ACTIVE,
            MemoryStatus.HISTORICAL,
            MemoryStatus.NEEDS_REVIEW,
        },
        MemoryStatus.NEEDS_REVIEW: {
            MemoryStatus.ACTIVE,
            MemoryStatus.HISTORICAL,
            MemoryStatus.STALE,
            MemoryStatus.CONTRADICTED,
        },
        MemoryStatus.HISTORICAL: {
            MemoryStatus.ACTIVE,
        },
    }

    def can_transition(
        self,
        current_status: MemoryStatus,
        new_status: MemoryStatus,
    ) -> bool:
        """
        Return whether a lifecycle transition is allowed.
        """

        return new_status in self.ALLOWED_TRANSITIONS.get(
            current_status,
            set(),
        )

    def transition(
        self,
        memory: Memory,
        new_status: MemoryStatus,
        reason: str,
    ) -> tuple[Memory, LifecycleTransition]:
        """
        Transition a memory to a new lifecycle state.

        Returns:
            A new Memory object and a LifecycleTransition record.

        Raises:
            LifecycleTransitionError:
                If the reason is empty or the transition is not allowed.
        """

        reason = reason.strip()

        if not reason:
            raise LifecycleTransitionError(
                "A lifecycle transition requires a non-empty reason."
            )

        current_status = memory.status

        if not self.can_transition(current_status, new_status):
            raise LifecycleTransitionError(
                f"Invalid lifecycle transition: "
                f"{current_status.value} -> {new_status.value}"
            )

        changed_at = utc_now()

        updated_memory = memory.model_copy(
            update={
                "status": new_status,
                "updated_at": changed_at,
            }
        )

        transition = LifecycleTransition(
            memory_id=memory.id,
            old_status=current_status,
            new_status=new_status,
            reason=reason,
            changed_at=changed_at,
        )

        return updated_memory, transition