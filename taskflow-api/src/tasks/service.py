"""Task Management Service for TaskFlow API."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class TaskItem:
    task_id: str
    title: str
    description: str
    owner_id: str
    status: str = "pending"  # "pending" | "in_progress" | "completed"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class TaskService:
    """Manages task creation, assignments, and status updates."""

    def __init__(self) -> None:
        self._tasks: dict[str, TaskItem] = {}

    def create_task(self, title: str, description: str, owner_id: str) -> TaskItem:
        """Create a new task item."""
        task_id = f"task_{len(self._tasks) + 1}"
        task = TaskItem(task_id=task_id, title=title, description=description, owner_id=owner_id)
        self._tasks[task_id] = task
        return task

    def get_user_tasks(self, owner_id: str) -> list[TaskItem]:
        """Fetch all tasks owned by a user."""
        return [task for task in self._tasks.values() if task.owner_id == owner_id]

    def update_task_status(self, task_id: str, new_status: str) -> TaskItem | None:
        """Update status of a task."""
        if task_id in self._tasks:
            self._tasks[task_id].status = new_status
            return self._tasks[task_id]
        return None
