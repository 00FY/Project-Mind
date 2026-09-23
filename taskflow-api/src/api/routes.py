"""API Routes for TaskFlow API."""

from taskflow-api.src.auth.service import AuthService
from taskflow-api.src.tasks.service import TaskService


class APIRouter:
    """REST API endpoints for TaskFlow API."""

    def __init__(self, auth: AuthService, tasks: TaskService) -> None:
        self.auth = auth
        self.tasks = tasks

    def handle_login(self, payload: dict) -> dict:
        """POST /api/v1/auth/login"""
        session = self.auth.login(payload.get("username", ""), payload.get("password", ""))
        if session:
            return {"status": "success", "token": session.token}
        return {"status": "error", "message": "Invalid credentials"}

    def handle_get_tasks(self, token: str) -> dict:
        """GET /api/v1/tasks"""
        session = self.auth.verify_token(token)
        if not session:
            return {"status": "error", "message": "Unauthorized"}
        user_tasks = self.tasks.get_user_tasks(session.user_id)
        return {"status": "success", "tasks": [t.__dict__ for t in user_tasks]}
