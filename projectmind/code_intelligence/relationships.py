"""Relationship extraction for ProjectMind code intelligence."""

from pathlib import Path

from projectmind.code_intelligence.models import (
    CodeEntity,
    CodeRelationship,
    RelationshipType,
)


class RelationshipExtractor:
    """Build relationships between extracted code entities."""

    def extract(
        self,
        entities: list[CodeEntity],
    ) -> list[CodeRelationship]:
        """Extract relationships from a collection of code entities."""
        relationships: list[CodeRelationship] = []

        relationships.extend(
            self._extract_contains(entities)
        )

        relationships.extend(
            self._extract_imports(entities)
        )

        return relationships

    @staticmethod
    def _extract_contains(
        entities: list[CodeEntity],
    ) -> list[CodeRelationship]:
        """Create contains relationships between classes and methods."""
        relationships: list[CodeRelationship] = []

        classes = [
            entity
            for entity in entities
            if entity.type.value == "class"
        ]

        methods = [
            entity
            for entity in entities
            if entity.type.value == "method"
        ]

        for method in methods:
            containing_classes = [
                class_entity
                for class_entity in classes
                if (
                    class_entity.file == method.file
                    and class_entity.line_start <= method.line_start
                    and class_entity.line_end >= method.line_end
                )
            ]

            if not containing_classes:
                continue

            containing_class = min(
                containing_classes,
                key=lambda entity: (
                    entity.line_end - entity.line_start
                ),
            )

            relationships.append(
                CodeRelationship(
                    source_entity_id=containing_class.entity_id,
                    target_entity_id=method.entity_id,
                    relationship_type=RelationshipType.CONTAINS,
                )
            )

        return relationships

    @staticmethod
    def _extract_imports(
        entities: list[CodeEntity],
    ) -> list[CodeRelationship]:
        """Create unique relationships between files and local imports."""
        relationships: list[CodeRelationship] = []
        seen_relationships: set[tuple[str, str]] = set()

        file_entities = [
            entity
            for entity in entities
            if entity.type.value == "file"
        ]

        import_entities = [
            entity
            for entity in entities
            if entity.type.value == "import"
        ]

        files_by_path = {
            entity.file: entity
            for entity in file_entities
        }

        for import_entity in import_entities:
            imported_paths = RelationshipExtractor._resolve_import_paths(
                import_entity.name,
                import_entity.file,
                files_by_path,
            )

            source_file = files_by_path.get(import_entity.file)

            if source_file is None:
                continue

            for imported_path in imported_paths:
                target_file = files_by_path.get(imported_path)

                if target_file is None:
                    continue

                relationship_key = (
                    source_file.entity_id,
                    target_file.entity_id,
                )

                if relationship_key in seen_relationships:
                    continue

                seen_relationships.add(relationship_key)

                relationships.append(
                    CodeRelationship(
                        source_entity_id=source_file.entity_id,
                        target_entity_id=target_file.entity_id,
                        relationship_type=RelationshipType.IMPORTS,
                    )
                )

        return relationships

    @staticmethod
    def _resolve_import_paths(
        import_statement: str,
        source_file: str,
        files_by_path: dict[str, CodeEntity],
    ) -> list[str]:
        """Resolve an import statement to repository-local Python files."""
        statement = import_statement.strip()

        if statement.startswith("from "):
            module_part = statement[5:].split(" import ", 1)[0].strip()
        elif statement.startswith("import "):
            module_part = statement[7:].strip().split(",", 1)[0].strip()
        else:
            return []

        if not module_part:
            return []

        source_directory = Path(source_file).parent

        if module_part.startswith("."):
            return RelationshipExtractor._resolve_relative_import(
                module_part,
                source_directory,
                files_by_path,
            )

        return RelationshipExtractor._resolve_absolute_import(
            module_part,
            files_by_path,
        )

    @staticmethod
    def _resolve_absolute_import(
        module_part: str,
        files_by_path: dict[str, CodeEntity],
    ) -> list[str]:
        """Resolve a repository-local absolute Python import."""
        module_path = module_part.replace(".", "/")

        candidates = [
            f"{module_path}.py",
            f"{module_path}/__init__.py",
        ]

        return [
            candidate
            for candidate in candidates
            if candidate in files_by_path
        ]

    @staticmethod
    def _resolve_relative_import(
        module_part: str,
        source_directory: Path,
        files_by_path: dict[str, CodeEntity],
    ) -> list[str]:
        """Resolve a relative Python import."""
        dot_count = len(module_part) - len(
            module_part.lstrip(".")
        )

        remainder = module_part[dot_count:]

        target_directory = source_directory

        for _ in range(max(dot_count - 1, 0)):
            target_directory = target_directory.parent

        if remainder:
            target_directory /= remainder.replace(".", "/")

        candidates = [
            f"{target_directory.as_posix()}.py",
            f"{target_directory.as_posix()}/__init__.py",
        ]

        return [
            candidate
            for candidate in candidates
            if candidate in files_by_path
        ]
