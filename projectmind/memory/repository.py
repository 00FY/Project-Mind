from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

from .constitution import ProjectConstitution
from .evidence import Evidence, EvidenceKind
from .enums import MemoryStatus, MemoryType, MemoryOrigin
from .models import Memory, utc_now

CURRENT_SCHEMA_VERSION = 3


class MemoryRepository:
    """
    SQLite repository responsible for persistent storage of:

    - project memories
    - evidence records
    - memory-evidence relationships

    Lifecycle logic such as stale detection, contradiction detection,
    and historical transitions is implemented separately.
    """

    def __init__(self, db_path: str | Path = "projectmind.db") -> None:
        self.db_path = Path(db_path)

        self._connection = sqlite3.connect(
            self.db_path,
            timeout=30,
        )

        self._connection.row_factory = sqlite3.Row

        self._connection.execute("PRAGMA foreign_keys = ON")

        self._initialize_database()

    def close(self) -> None:
        """Close the SQLite connection."""
        self._connection.close()

    def __enter__(self) -> "MemoryRepository":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    # ------------------------------------------------------------------
    # DATABASE INITIALIZATION
    # ------------------------------------------------------------------
    def _initialize_database(self) -> None:
        """
        Initialize or migrate the ProjectMind database schema.
        """

        version = self._get_schema_version()

        if version > CURRENT_SCHEMA_VERSION:
            raise RuntimeError(
                f"Database schema version {version} is newer than "
                f"supported version {CURRENT_SCHEMA_VERSION}."
            )

        if version == 0:
            if self._database_has_tables():
                self._upgrade_legacy_database()
            else:
                self._create_schema_v1()

            self._set_schema_version(1)
            version = 1

        while version < CURRENT_SCHEMA_VERSION:
            next_version = version + 1

            if next_version == 2:
                self._migrate_v1_to_v2()

            if next_version == 3:
                self._migrate_v2_to_v3()

            self._set_schema_version(next_version)
            version = next_version

    def _get_schema_version(self) -> int:
        row = self._connection.execute("PRAGMA user_version").fetchone()

        return row[0]

    def _set_schema_version(self, version: int) -> None:
        self._connection.execute(f"PRAGMA user_version = {version}")

    def _database_has_tables(self) -> bool:
        row = self._connection.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table'
            AND name NOT LIKE 'sqlite_%'
            LIMIT 1
            """
        ).fetchone()

        return row is not None

    def _upgrade_legacy_database(self) -> None:
        """
        Adopt an existing unversioned ProjectMind database
        as schema version 1.
        """

        required_tables = {
            "memories",
            "evidence",
            "memory_evidence",
            "memory_transitions",
        }

        existing_tables = {
            row["name"]
            for row in self._connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                AND name NOT LIKE 'sqlite_%'
                """
            ).fetchall()
        }

        missing_tables = required_tables - existing_tables

        if missing_tables:
            raise RuntimeError(
                "Existing database is missing required tables: " + ", ".join(sorted(missing_tables))
            )

        self._migrate_memory_evidence_foreign_key()

    def _migrate_memory_evidence_foreign_key(self) -> None:
        """
        Upgrade an existing memory_evidence table from
        ON DELETE CASCADE to ON DELETE RESTRICT.

        Existing relationship rows are preserved.
        """

        foreign_keys = self._connection.execute(
            """
            PRAGMA foreign_key_list(memory_evidence)
            """
        ).fetchall()

        evidence_foreign_key = None

        for foreign_key in foreign_keys:
            referenced_table = foreign_key["table"]
            from_column = foreign_key["from"]

            if referenced_table == "evidence" and from_column == "evidence_id":
                evidence_foreign_key = foreign_key
                break

        if evidence_foreign_key is None:
            return

        # SQLite foreign-key metadata uses:
        # 0 = NO ACTION
        # 1 = RESTRICT
        # 2 = SET NULL
        # 3 = SET DEFAULT
        # 4 = CASCADE
        # 5 = SET NULL in older representations depending on version.
        #
        # We only need to migrate when the current action is CASCADE.
        if evidence_foreign_key["on_delete"] != "CASCADE":
            return

        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE memory_evidence_new (
                    memory_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,

                    PRIMARY KEY (memory_id, evidence_id),

                    FOREIGN KEY (memory_id)
                        REFERENCES memories(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (evidence_id)
                        REFERENCES evidence(id)
                        ON DELETE RESTRICT
                )
                """
            )

            self._connection.execute(
                """
                INSERT INTO memory_evidence_new (
                    memory_id,
                    evidence_id
                )
                SELECT
                    memory_id,
                    evidence_id
                FROM memory_evidence
                """
            )

            self._connection.execute(
                """
                DROP TABLE memory_evidence
                """
            )

            self._connection.execute(
                """
                ALTER TABLE memory_evidence_new
                RENAME TO memory_evidence
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_evidence_memory
                    ON memory_evidence(memory_id)
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_evidence_evidence
                    ON memory_evidence(evidence_id)
                """
            )

    def _create_schema_v1(self) -> None:
        """
        Create the ProjectMind database schema version 1.
        """

        with self._connection:
            self._connection.executescript(
                """
                CREATE TABLE memories (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    importance REAL NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_verified_at TEXT,
                    observed_at_commit TEXT,
                    valid_from TEXT,
                    valid_until TEXT,
                    related_entities TEXT NOT NULL
                );

                CREATE TABLE evidence (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    file_path TEXT,
                    symbol TEXT,
                    "commit" TEXT,
                    line_start INTEGER,
                    line_end INTEGER,
                    description TEXT
                );

                CREATE TABLE memory_evidence (
                    memory_id TEXT NOT NULL,
                    evidence_id TEXT NOT NULL,

                    PRIMARY KEY (memory_id, evidence_id),

                    FOREIGN KEY (memory_id)
                        REFERENCES memories(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (evidence_id)
                        REFERENCES evidence(id)
                        ON DELETE RESTRICT
                );

                CREATE INDEX idx_memory_evidence_memory
                    ON memory_evidence(memory_id);

                CREATE INDEX idx_memory_evidence_evidence
                    ON memory_evidence(evidence_id);

                CREATE TABLE memory_transitions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    memory_id TEXT NOT NULL,
                    old_status TEXT NOT NULL,
                    new_status TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    changed_at TEXT NOT NULL,

                    FOREIGN KEY (memory_id)
                        REFERENCES memories(id)
                        ON DELETE CASCADE
                );

                CREATE INDEX idx_memory_transitions_memory
                    ON memory_transitions(memory_id);

                CREATE INDEX idx_memory_transitions_changed_at
                    ON memory_transitions(changed_at);
                """
            )

    def _migrate_v1_to_v2(self) -> None:
        """
        Upgrade schema version 1 to schema version 2.

        Adds:
        - memory_entities
        - project_constitution

        Existing related_entities JSON is backfilled into
        memory_entities.
        """

        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entities (
                    memory_id TEXT NOT NULL,
                    entity TEXT NOT NULL,

                    PRIMARY KEY (memory_id, entity),

                    FOREIGN KEY (memory_id)
                        REFERENCES memories(id)
                        ON DELETE CASCADE
                )
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_entities_entity
                ON memory_entities(entity)
                """
            )

            self._connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_memory_entities_memory
                ON memory_entities(memory_id)
                """
            )

            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_constitution (
                    version INTEGER PRIMARY KEY,
                    goal TEXT NOT NULL,
                    requirements TEXT NOT NULL,
                    architecture TEXT NOT NULL,
                    constraints TEXT NOT NULL,
                    decisions TEXT NOT NULL,
                    non_goals TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            rows = self._connection.execute(
                """
                SELECT id, related_entities
                FROM memories
                """
            ).fetchall()

            for row in rows:
                entities = json.loads(row["related_entities"])

                self._connection.executemany(
                    """
                    INSERT OR IGNORE INTO memory_entities (
                        memory_id,
                        entity
                    )
                    VALUES (?, ?)
                    """,
                    [(row["id"], entity) for entity in dict.fromkeys(entities)],
                )

    def _migrate_v2_to_v3(self) -> None:
        """
        Upgrade schema version 2 to schema version 3.

        Adds structured fact fields and invalidation timestamp
        to the memories table.
        """

        with self._connection:
            self._connection.execute(
                """
                ALTER TABLE memories
                ADD COLUMN subject TEXT
                """
            )

            self._connection.execute(
                """
                ALTER TABLE memories
                ADD COLUMN value TEXT
                """
            )

            self._connection.execute(
                """
                ALTER TABLE memories
                ADD COLUMN origin TEXT
                """
            )

            self._connection.execute(
                """
                ALTER TABLE memories
                ADD COLUMN invalidated_at TEXT
                """
            )

    # ------------------------------------------------------------------
    # DATETIME HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _datetime_to_string(
        value: Optional[datetime],
    ) -> Optional[str]:
        """
        Convert a timezone-aware Python datetime to ISO-8601.

        Memory validation guarantees that Memory datetime fields
        are timezone-aware before they reach the repository.
        """

        if value is None:
            return None

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ProjectMind datetimes must be timezone-aware.")

        return value.isoformat()

    @staticmethod
    def _string_to_datetime(
        value: Optional[str],
    ) -> Optional[datetime]:
        """
        Convert an ISO-8601 SQLite string into a Python datetime.
        """

        if value is None:
            return None

        parsed = datetime.fromisoformat(value)

        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("Stored ProjectMind datetime is not timezone-aware.")

        return parsed

    # ------------------------------------------------------------------
    # MEMORY CONVERSION HELPERS
    # ------------------------------------------------------------------

    def _row_to_memory(
        self,
        row: sqlite3.Row,
    ) -> Memory:
        """
        Convert a SQLite memory row into a Pydantic Memory object.
        """

        evidence_ids = self._get_evidence_ids_for_memory(row["id"])

        related_entities = self._get_entities_for_memory(row["id"])

        return Memory(
            id=row["id"],
            type=MemoryType(row["type"]),
            content=row["content"],
            subject=row["subject"],
            value=row["value"],
            origin=(MemoryOrigin(row["origin"]) if row["origin"] is not None else None),
            importance=row["importance"],
            confidence=row["confidence"],
            status=MemoryStatus(row["status"]),
            created_at=self._string_to_datetime(row["created_at"]),
            updated_at=self._string_to_datetime(row["updated_at"]),
            invalidated_at=self._string_to_datetime(row["invalidated_at"]),
            last_verified_at=self._string_to_datetime(row["last_verified_at"]),
            observed_at_commit=row["observed_at_commit"],
            valid_from=self._string_to_datetime(row["valid_from"]),
            valid_until=self._string_to_datetime(row["valid_until"]),
            evidence=evidence_ids,
            related_entities=related_entities,
        )

    # ------------------------------------------------------------------
    # MEMORY CRUD
    # ------------------------------------------------------------------

    def create_memory(
        self,
        memory: Memory,
    ) -> Memory:
        """
        Insert a new memory into SQLite.

        Evidence IDs referenced by the memory must already exist.
        """

        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO memories (
                        id,
                        type,
                        content,
                        importance,
                        confidence,
                        status,
                        created_at,
                        updated_at,
                        last_verified_at,
                        observed_at_commit,
                        valid_from,
                        valid_until,
                        related_entities,
                        subject,
                        value,
                        origin,
                        invalidated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        memory.id,
                        memory.type.value,
                        memory.content,
                        memory.importance,
                        memory.confidence,
                        memory.status.value,
                        self._datetime_to_string(memory.created_at),
                        self._datetime_to_string(memory.updated_at),
                        self._datetime_to_string(memory.last_verified_at),
                        memory.observed_at_commit,
                        self._datetime_to_string(memory.valid_from),
                        self._datetime_to_string(memory.valid_until),
                        json.dumps(memory.related_entities),
                        memory.subject,
                        memory.value,
                        memory.origin.value if memory.origin else None,
                        self._datetime_to_string(memory.invalidated_at),
                    ),
                )

                self._replace_memory_evidence(
                    memory.id,
                    memory.evidence,
                )

                self._replace_memory_entities(
                    memory.id,
                    memory.related_entities,
                )

        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Memory '{memory.id}' could not be created.") from exc

        return self.get_memory(memory.id)

    def get_memory(
        self,
        memory_id: str,
    ) -> Memory:
        """
        Retrieve a memory by ID.
        """

        row = self._connection.execute(
            """
            SELECT *
            FROM memories
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()

        if row is None:
            raise KeyError(f"Memory '{memory_id}' does not exist.")

        return self._row_to_memory(row)

    def list_memories(
        self,
        status: Optional[MemoryStatus] = None,
        memory_type: Optional[MemoryType] = None,
    ) -> list[Memory]:
        """
        Return memories, optionally filtered by status and/or type.
        """

        query = """
            SELECT *
            FROM memories
            WHERE 1 = 1
        """

        parameters: list[str] = []

        if status is not None:
            query += " AND status = ?"
            parameters.append(status.value)

        if memory_type is not None:
            query += " AND type = ?"
            parameters.append(memory_type.value)

        query += """
            ORDER BY created_at ASC, id ASC
        """

        rows = self._connection.execute(
            query,
            parameters,
        ).fetchall()

        return [self._row_to_memory(row) for row in rows]

    def list_memories_by_entity(
        self,
        entity: str,
    ) -> list[Memory]:
        """
        Return all memories associated with an entity.

        Uses the indexed memory_entities table rather than
        scanning and parsing the related_entities JSON column.
        """

        rows = self._connection.execute(
            """
            SELECT m.*
            FROM memories m
            INNER JOIN memory_entities me
                ON me.memory_id = m.id
            WHERE me.entity = ?
            ORDER BY m.created_at ASC, m.id ASC
            """,
            (entity,),
        ).fetchall()

        return [self._row_to_memory(row) for row in rows]

    def _update_memory_in_transaction(
        self,
        memory: Memory,
    ) -> None:
        """
        Update a memory using the repository's current transaction.

        This method does not commit. The caller owns the transaction.
        """

        cursor = self._connection.execute(
            """
            UPDATE memories
            SET
                type = ?,
                content = ?,
                importance = ?,
                confidence = ?,
                status = ?,
                created_at = ?,
                updated_at = ?,
                last_verified_at = ?,
                observed_at_commit = ?,
                valid_from = ?,
                valid_until = ?,
                related_entities = ?,
                subject = ?,
                value = ?,
                origin = ?,
                invalidated_at = ?
            WHERE id = ?
            """,
            (
                memory.type.value,
                memory.content,
                memory.importance,
                memory.confidence,
                memory.status.value,
                self._datetime_to_string(memory.created_at),
                self._datetime_to_string(memory.updated_at),
                self._datetime_to_string(memory.last_verified_at),
                memory.observed_at_commit,
                self._datetime_to_string(memory.valid_from),
                self._datetime_to_string(memory.valid_until),
                json.dumps(memory.related_entities),
                memory.subject,
                memory.value,
                memory.origin.value if memory.origin else None,
                self._datetime_to_string(memory.invalidated_at),
                memory.id,
            ),
        )

        if cursor.rowcount == 0:
            raise KeyError(f"Memory '{memory.id}' does not exist.")

        self._replace_memory_evidence(
            memory.id,
            memory.evidence,
        )

        self._replace_memory_entities(
            memory.id,
            memory.related_entities,
        )

    def update_memory(
        self,
        memory: Memory,
    ) -> None:
        """
        Update an existing memory as one standalone transaction.
        """

        try:
            with self._connection:
                self._update_memory_in_transaction(memory)

        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Memory '{memory.id}' could not be updated.") from exc

    def delete_memory(
        self,
        memory_id: str,
    ) -> None:
        """
        Permanently delete a memory.

        Lifecycle logic should normally prefer marking memories
        as HISTORICAL rather than physically deleting them.
        """

        with self._connection:
            cursor = self._connection.execute(
                """
                DELETE FROM memories
                WHERE id = ?
                """,
                (memory_id,),
            )

            if cursor.rowcount == 0:
                raise KeyError(f"Memory '{memory_id}' does not exist.")

    # ------------------------------------------------------------------
    # EVIDENCE CRUD
    # ------------------------------------------------------------------

    def create_evidence(
        self,
        evidence: Evidence,
    ) -> Evidence:
        """
        Insert an evidence record into SQLite.
        """

        try:
            with self._connection:
                self._connection.execute(
                    """
                    INSERT INTO evidence (
                        id,
                        kind,
                        file_path,
                        symbol,
                        "commit",
                        line_start,
                        line_end,
                        description
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        evidence.id,
                        evidence.kind.value,
                        evidence.file_path,
                        evidence.symbol,
                        evidence.commit,
                        evidence.line_start,
                        evidence.line_end,
                        evidence.description,
                    ),
                )

        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Evidence '{evidence.id}' could not be created.") from exc

        return self.get_evidence(evidence.id)

    def get_evidence(
        self,
        evidence_id: str,
    ) -> Evidence:
        """
        Retrieve evidence by ID.
        """

        row = self._connection.execute(
            """
            SELECT
                id,
                kind,
                file_path,
                symbol,
                "commit",
                line_start,
                line_end,
                description
            FROM evidence
            WHERE id = ?
            """,
            (evidence_id,),
        ).fetchone()

        if row is None:
            raise KeyError(f"Evidence '{evidence_id}' does not exist.")

        return Evidence(
            id=row["id"],
            kind=EvidenceKind(row["kind"]),
            file_path=row["file_path"],
            symbol=row["symbol"],
            commit=row["commit"],
            line_start=row["line_start"],
            line_end=row["line_end"],
            description=row["description"],
        )

    def list_evidence(self) -> list[Evidence]:
        """
        Return all evidence records.
        """

        rows = self._connection.execute(
            """
            SELECT
                id,
                kind,
                file_path,
                symbol,
                "commit",
                line_start,
                line_end,
                description
            FROM evidence
            ORDER BY id ASC
            """
        ).fetchall()

        return [
            Evidence(
                id=row["id"],
                kind=EvidenceKind(row["kind"]),
                file_path=row["file_path"],
                symbol=row["symbol"],
                commit=row["commit"],
                line_start=row["line_start"],
                line_end=row["line_end"],
                description=row["description"],
            )
            for row in rows
        ]

    def update_evidence(
        self,
        evidence: Evidence,
    ) -> None:
        """
        Update an existing evidence record.
        """

        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    UPDATE evidence
                    SET
                        kind = ?,
                        file_path = ?,
                        symbol = ?,
                        "commit" = ?,
                        line_start = ?,
                        line_end = ?,
                        description = ?
                    WHERE id = ?
                    """,
                    (
                        evidence.kind.value,
                        evidence.file_path,
                        evidence.symbol,
                        evidence.commit,
                        evidence.line_start,
                        evidence.line_end,
                        evidence.description,
                        evidence.id,
                    ),
                )

                if cursor.rowcount == 0:
                    raise KeyError(f"Evidence '{evidence.id}' does not exist.")

        except sqlite3.IntegrityError as exc:
            raise ValueError(f"Evidence '{evidence.id}' could not be updated.") from exc

    def delete_evidence(
        self,
        evidence_id: str,
    ) -> None:
        """
        Delete evidence only when it is not referenced by a memory.

        Because memory_evidence uses ON DELETE RESTRICT for evidence,
        SQLite will reject deletion while any memory still references
        this evidence.
        """

        try:
            with self._connection:
                cursor = self._connection.execute(
                    """
                    DELETE FROM evidence
                    WHERE id = ?
                    """,
                    (evidence_id,),
                )

                if cursor.rowcount == 0:
                    raise KeyError(f"Evidence '{evidence_id}' does not exist.")

        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Evidence '{evidence_id}' cannot be deleted "
                "because it is still linked to one or more memories."
            ) from exc

    # ------------------------------------------------------------------
    # MEMORY-EVIDENCE RELATIONSHIPS
    # ------------------------------------------------------------------

    def _get_evidence_ids_for_memory(
        self,
        memory_id: str,
    ) -> list[str]:
        """
        Retrieve all evidence IDs associated with a memory.
        """

        rows = self._connection.execute(
            """
            SELECT evidence_id
            FROM memory_evidence
            WHERE memory_id = ?
            ORDER BY evidence_id ASC
            """,
            (memory_id,),
        ).fetchall()

        return [row["evidence_id"] for row in rows]

    def _get_entities_for_memory(
        self,
        memory_id: str,
    ) -> list[str]:
        """
        Retrieve all entities associated with a memory.
        """

        rows = self._connection.execute(
            """
            SELECT entity
            FROM memory_entities
            WHERE memory_id = ?
            ORDER BY entity ASC
            """,
            (memory_id,),
        ).fetchall()

        return [row["entity"] for row in rows]

    def _replace_memory_evidence(
        self,
        memory_id: str,
        evidence_ids: list[str],
    ) -> None:
        """
        Replace the evidence relationships for a memory.

        Every referenced evidence ID must already exist.
        """

        unique_evidence_ids = list(dict.fromkeys(evidence_ids))

        if unique_evidence_ids:
            placeholders = ", ".join("?" for _ in unique_evidence_ids)

            rows = self._connection.execute(
                f"""
                SELECT id
                FROM evidence
                WHERE id IN ({placeholders})
                """,
                unique_evidence_ids,
            ).fetchall()

            existing_ids = {row["id"] for row in rows}

            missing_ids = [
                evidence_id
                for evidence_id in unique_evidence_ids
                if evidence_id not in existing_ids
            ]

            if missing_ids:
                raise ValueError(
                    "Cannot link memory to missing evidence: " + ", ".join(missing_ids)
                )

        self._connection.execute(
            """
            DELETE FROM memory_evidence
            WHERE memory_id = ?
            """,
            (memory_id,),
        )

        if unique_evidence_ids:
            self._connection.executemany(
                """
                INSERT INTO memory_evidence (
                    memory_id,
                    evidence_id
                )
                VALUES (?, ?)
                """,
                [(memory_id, evidence_id) for evidence_id in unique_evidence_ids],
            )

    def _replace_memory_entities(
        self,
        memory_id: str,
        entities: list[str],
    ) -> None:
        """
        Replace the entity relationships for a memory.

        Empty or whitespace-only entities are ignored.
        Duplicate entities are removed while preserving order.
        """

        unique_entities = list(
            dict.fromkeys(entity.strip() for entity in entities if entity.strip())
        )

        self._connection.execute(
            """
            DELETE FROM memory_entities
            WHERE memory_id = ?
            """,
            (memory_id,),
        )

        if unique_entities:
            self._connection.executemany(
                """
                INSERT INTO memory_entities (
                    memory_id,
                    entity
                )
                VALUES (?, ?)
                """,
                [(memory_id, entity) for entity in unique_entities],
            )

    def _create_transition_log_in_transaction(
        self,
        transition,
    ) -> None:
        """
        Insert a lifecycle transition using the current transaction.

        This method does not commit.
        """

        self._connection.execute(
            """
            INSERT INTO memory_transitions (
                memory_id,
                old_status,
                new_status,
                reason,
                changed_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                transition.memory_id,
                transition.old_status.value,
                transition.new_status.value,
                transition.reason,
                self._datetime_to_string(transition.changed_at),
            ),
        )

    def apply_lifecycle_transition(
        self,
        memory: Memory,
        transition,
    ) -> None:
        """
        Atomically persist a memory lifecycle transition.

        The memory update and transition audit record are committed
        together or rolled back together.
        """

        try:
            with self._connection:
                self._update_memory_in_transaction(memory)

                self._create_transition_log_in_transaction(transition)

        except sqlite3.IntegrityError as exc:
            raise ValueError(
                f"Lifecycle transition for memory '{memory.id}' could not be persisted."
            ) from exc

    def list_transition_logs(
        self,
        memory_id: str,
    ) -> list[dict]:
        """
        Return lifecycle transition history for a memory.
        """

        rows = self._connection.execute(
            """
            SELECT
                id,
                memory_id,
                old_status,
                new_status,
                reason,
                changed_at
            FROM memory_transitions
            WHERE memory_id = ?
            ORDER BY id ASC
            """,
            (memory_id,),
        ).fetchall()

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # PROJECT CONSTITUTION
    # ------------------------------------------------------------------

    def save_constitution(
        self,
        constitution: ProjectConstitution,
    ) -> int:
        """
        Append a new project constitution version.

        Constitution history is immutable. Each save creates
        a new version rather than updating an existing one.

        Returns:
            The newly created version number.
        """

        with self._connection:
            row = self._connection.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                FROM project_constitution
                """
            ).fetchone()

            version = row["next_version"]

            self._connection.execute(
                """
                INSERT INTO project_constitution (
                    version,
                    goal,
                    requirements,
                    architecture,
                    constraints,
                    decisions,
                    non_goals,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version,
                    constitution.goal,
                    json.dumps(constitution.requirements),
                    json.dumps(constitution.architecture),
                    json.dumps(constitution.constraints),
                    json.dumps(constitution.decisions),
                    json.dumps(constitution.non_goals),
                    self._datetime_to_string(utc_now()),
                ),
            )

        return version

    def get_constitution(
        self,
        version: Optional[int] = None,
    ) -> ProjectConstitution:
        """
        Retrieve a project constitution.

        If version is None, return the latest constitution.
        """

        if version is None:
            row = self._connection.execute(
                """
                SELECT *
                FROM project_constitution
                ORDER BY version DESC
                LIMIT 1
                """
            ).fetchone()
        else:
            row = self._connection.execute(
                """
                SELECT *
                FROM project_constitution
                WHERE version = ?
                """,
                (version,),
            ).fetchone()

        if row is None:
            raise KeyError("Requested project constitution does not exist.")

        return ProjectConstitution(
            goal=row["goal"],
            requirements=json.loads(row["requirements"]),
            architecture=json.loads(row["architecture"]),
            constraints=json.loads(row["constraints"]),
            decisions=json.loads(row["decisions"]),
            non_goals=json.loads(row["non_goals"]),
        )
