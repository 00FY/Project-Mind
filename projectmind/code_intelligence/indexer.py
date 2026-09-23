"""Repository indexing pipeline for ProjectMind code intelligence."""

from hashlib import sha1
from pathlib import Path

from projectmind.code_intelligence.entities import PythonEntityExtractor
from projectmind.code_intelligence.models import (
    CodeEntity,
    CodeRelationship,
    EntityType,
    ScannedFile,
)
from projectmind.code_intelligence.relationships import RelationshipExtractor
from projectmind.code_intelligence.scanner import RepositoryScanner


class CodeIndexer:
    """Coordinate repository scanning and code entity extraction."""

    def __init__(self, project_root: str | Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.scanner = RepositoryScanner(self.project_root)
        self.extractor = PythonEntityExtractor()
        self.relationship_extractor = RelationshipExtractor()
        self.relationships: list[CodeRelationship] = []

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

            entities.append(
                self._create_file_entity(scanned_file)
            )

            file_entities = self._extract_file(scanned_file)
            entities.extend(file_entities)

        self.relationships = self.relationship_extractor.extract(entities)

        return entities

    def _extract_file(
        self,
        scanned_file: ScannedFile,
    ) -> list[CodeEntity]:
        """Read one source file and extract its entities."""
        file_path = self.project_root / scanned_file.path
        source_code = file_path.read_text(encoding="utf-8")

        return self.extractor.extract(
            source_code=source_code,
            file_path=scanned_file.path,
        )


    def _create_file_entity(
    self,
    scanned_file: ScannedFile,
    ) -> CodeEntity:
        """Create a CodeEntity representing a source file."""
        file_path = scanned_file.path

        raw_id = f"{file_path}:file"
        entity_id = sha1(
            raw_id.encode("utf-8")
        ).hexdigest()[:12]

        source_path = self.project_root / file_path

        try:
            line_count = len(
                source_path.read_text(
                    encoding="utf-8",
                ).splitlines()
            )
        except (OSError, UnicodeDecodeError):
            line_count = 1

        return CodeEntity(
            entity_id=entity_id,
            type=EntityType.FILE,
            name=Path(file_path).stem,
            file=file_path,
            line_start=1,
            line_end=max(line_count, 1),
            language=scanned_file.language,
        )
