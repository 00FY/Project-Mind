"""Repository indexing pipeline for ProjectMind code intelligence."""

from pathlib import Path

from projectmind.code_intelligence.entities import PythonEntityExtractor
from projectmind.code_intelligence.models import CodeEntity, ScannedFile
from projectmind.code_intelligence.scanner import RepositoryScanner


class CodeIndexer:
    """Coordinate repository scanning and code entity extraction."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.scanner = RepositoryScanner(self.project_root)
        self.extractor = PythonEntityExtractor()

    def index(self) -> list[CodeEntity]:
        """
        Scan the repository and extract entities from supported source files.

        Currently, Python files are parsed with Tree-sitter.
        """
        scanned_files = self.scanner.scan()
        entities: list[CodeEntity] = []

        for scanned_file in scanned_files:
            if scanned_file.language != "python":
                continue

            file_entities = self._extract_file(scanned_file)
            entities.extend(file_entities)

        return entities

    def _extract_file(self, scanned_file: ScannedFile) -> list[CodeEntity]:
        """Read one source file and extract its entities."""
        file_path = self.project_root / scanned_file.path

        source_code = file_path.read_text(encoding="utf-8")

        return self.extractor.extract(
            source_code=source_code,
            file_path=scanned_file.path,
        )
