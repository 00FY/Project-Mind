"""Database connection manager for TaskFlow API."""

import sqlite3
from pathlib import Path


class DatabaseManager:
    """Manages SQLite database connections and schema migrations for TaskFlow API."""

    def __init__(self, db_path: str = "taskflow.db") -> None:
        self.db_path = Path(db_path)

    def get_connection(self) -> sqlite3.Connection:
        """Open a parameterized database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self) -> None:
        """Create users and tasks database tables."""
        with self.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    FOREIGN KEY(owner_id) REFERENCES users(user_id)
                )
                """
            )
