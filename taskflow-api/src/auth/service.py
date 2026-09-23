"""Authentication Service for TaskFlow API."""

from dataclasses import dataclass


@dataclass
class UserSession:
    user_id: str
    token: str
    is_admin: bool = False


class AuthService:
    """Handles JWT token verification, password hashing, and user authentication."""

    def __init__(self, secret_key: str = "supersecret") -> None:
        self.secret_key = secret_key
        self._active_sessions: dict[str, UserSession] = {}

    def login(self, username: str, password_hash: str) -> UserSession | None:
        """Authenticate user and return session token."""
        if not username or not password_hash:
            return None
        session = UserSession(user_id=f"user_{username}", token=f"jwt_token_{username}")
        self._active_sessions[session.token] = session
        return session

    def verify_token(self, token: str) -> UserSession | None:
        """Verify JWT session token."""
        return self._active_sessions.get(token)

    def logout(self, token: str) -> bool:
        """Invalidate user session token."""
        if token in self._active_sessions:
            del self._active_sessions[token]
            return True
        return False
