"""Public Code Intelligence service for ProjectMind."""

from datetime import UTC, datetime
from pathlib import Path

from projectmind.code_intelligence.indexer import CodeIndexer
from projectmind.code_intelligence.models import (
    CodeEntity,
    CodeRelationship,
)
from projectmind.code_intelligence.scanner import RepositoryScanner
from projectmind.core.interfaces import (
    CodeChunk,
    CodeIntelligence,
    FileSummary,
    GitChange,
    IndexResult,
)


class CodeIntelligenceService(CodeIntelligence):
    """Concrete Member 1 implementation of the shared CodeIntelligence API."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.indexer = CodeIndexer(self.project_root)
        self.scanner = RepositoryScanner(self.project_root)
        self._entities: list[CodeEntity] = []
        self._last_indexed: datetime | None = None

    def index_project(self, project_root: str) -> IndexResult:
        """Index the project and extract code entities and relationships."""
        start = datetime.now(UTC)

        root = Path(project_root).resolve()

        if root != self.project_root:
            self.project_root = root
            self.indexer = CodeIndexer(root)
            self.scanner = RepositoryScanner(root)

        scanned_files = self.scanner.scan()

        self._entities = self.indexer.index()

        self._last_indexed = datetime.now(UTC)

        duration = (
            self._last_indexed - start
        ).total_seconds()

        return IndexResult(
            files_indexed=len(scanned_files),
            files_skipped=0,
            duration_seconds=duration,
        )

    def get_file_summary(self, file_path: str) -> FileSummary:
        """Return a summary of a source file."""
        path = self.project_root / file_path

        entities = [
            entity
            for entity in self._entities
            if entity.file == file_path
        ]

        functions = [
            entity.name
            for entity in entities
            if entity.type.value == "function"
        ]

        classes = [
            entity.name
            for entity in entities
            if entity.type.value == "class"
        ]

        imports = [
            entity.name
            for entity in entities
            if entity.type.value == "import"
        ]

        language = (
            "python"
            if path.suffix.lower() == ".py"
            else "unknown"
        )

        return FileSummary(
            path=file_path,
            language=language,
            functions=functions,
            classes=classes,
            imports=imports,
            last_modified=datetime.fromtimestamp(
                path.stat().st_mtime,
                tz=UTC,
            ),
        )

    def get_related_code(
        self,
        query: str,
        limit: int = 5,
    ) -> list[CodeChunk]:
        """Return code chunks whose entity names match the query."""
        query_lower = query.lower()

        matches = [
            entity
            for entity in self._entities
            if query_lower in entity.name.lower()
        ][:limit]

        results: list[CodeChunk] = []

        for entity in matches:
            path = self.project_root / entity.file

            try:
                lines = path.read_text(
                    encoding="utf-8",
                ).splitlines()
            except (OSError, UnicodeDecodeError):
                continue

            start = entity.line_start
            end = min(
                entity.line_end,
                len(lines),
            )

            content = "\n".join(
                lines[start - 1:end],
            )

            results.append(
                CodeChunk(
                    file_path=entity.file,
                    start_line=start,
                    end_line=end,
                    content=content,
                    language=entity.language,
                    relevance_score=1.0,
                    summary=(
                        f"{entity.type.value}: "
                        f"{entity.name}"
                    ),
                )
            )

        return results

    def get_git_changes(
        self,
        since_commit: str = "HEAD~1",
    ) -> list[GitChange]:
        """
        Return recent Git changes.

        Git change tracking will be implemented in the
        next Member 1 stage.
        """
        return []

    def get_last_indexed(self) -> datetime | None:
        """Return the timestamp of the most recent successful index."""
        return self._last_indexed

    @property
    def entities(self) -> list[CodeEntity]:
        """Return entities discovered during the latest index."""
        return self._entities

    @property
    def relationships(self) -> list[CodeRelationship]:
        """Return relationships discovered during the latest index."""
        return self.indexer.relationships
