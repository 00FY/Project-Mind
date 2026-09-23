from .enums import MemoryStatus
from .lifecycle import (
    LifecycleTransition,
    MemoryLifecycleEngine,
)
from .models import Memory
from .repository import MemoryRepository


class MemoryTransitionService:
    """
    Coordinates lifecycle decisions with persistent storage.

    The lifecycle engine determines whether a transition is valid.
    The transition service applies temporal semantics.
    The repository atomically persists the resulting state and
    transition history.
    """

    def __init__(
        self,
        repository: MemoryRepository,
        lifecycle_engine: MemoryLifecycleEngine | None = None,
    ) -> None:
        self.repository = repository
        self.lifecycle_engine = (
            lifecycle_engine
            or MemoryLifecycleEngine()
        )

    def transition(
        self,
        memory_id: str,
        new_status: MemoryStatus,
        reason: str,
    ) -> tuple[Memory, LifecycleTransition]:
        """
        Apply and atomically persist a lifecycle transition.
        """

        memory = self.repository.get_memory(
            memory_id
        )

        updated_memory, transition = (
            self.lifecycle_engine.transition(
                memory,
                new_status,
                reason,
            )
        )

        if new_status == MemoryStatus.HISTORICAL:
            updated_memory = updated_memory.model_copy(
                update={
                    "valid_until": transition.changed_at,
                }
            )

        self.repository.apply_lifecycle_transition(
            updated_memory,
            transition,
        )

        return updated_memory, transition