"""Relationship extraction for ProjectMind code intelligence."""

from pathlib import Path

from projectmind.code_intelligence.models import (
    CodeEntity,
    CodeRelationship,
    RelationshipType,
)
from projectmind.code_intelligence.parser import PythonParser


class RelationshipExtractor:
    """Build relationships between extracted code entities."""

    def __init__(self) -> None:
        self.parser = PythonParser()

    def extract(
        self,
        entities: list[CodeEntity],
        source_files: dict[str, str] | None = None,
    ) -> list[CodeRelationship]:
        """
        Extract relationships from code entities and source files.

        Args:
            entities: Code entities extracted from the repository.
            source_files: Mapping of repository-relative file paths to
                their source code. Required for inheritance relationships.

        Returns:
            A list of code relationships.
        """
        relationships: list[CodeRelationship] = []

        relationships.extend(
            self._extract_contains(entities)
        )

        relationships.extend(
            self._extract_imports(entities)
        )

        if source_files is not None:
            relationships.extend(
                self._extract_inherits(
                    entities,
                    source_files,
                )
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

    def _extract_inherits(
        self,
        entities: list[CodeEntity],
        source_files: dict[str, str],
    ) -> list[CodeRelationship]:
        """
        Create inheritance relationships between class entities.

        The first implementation resolves:
        - base classes defined in the same file;
        - base classes whose name is unique across the repository.

        Ambiguous class names are ignored rather than producing a
        potentially incorrect relationship.
        """
        relationships: list[CodeRelationship] = []
        seen_relationships: set[tuple[str, str]] = set()

        classes = [
            entity
            for entity in entities
            if entity.type.value == "class"
        ]

        classes_by_name: dict[str, list[CodeEntity]] = {}

        for class_entity in classes:
            classes_by_name.setdefault(
                class_entity.name,
                [],
            ).append(class_entity)

        for file_path, source_code in source_files.items():
            file_classes = [
                entity
                for entity in classes
                if entity.file == file_path
            ]

            if not file_classes:
                continue

            tree = self.parser.parse(source_code)

            for node in self._walk_class_definitions(
                tree.root_node,
            ):
                class_name = self._get_node_text(
                    node.child_by_field_name("name"),
                    source_code,
                )

                if class_name is None:
                    continue

                source_class = self._find_class_entity(
                    file_classes,
                    class_name,
                )

                if source_class is None:
                    continue

                superclasses_node = node.child_by_field_name(
                    "superclasses"
                )

                if superclasses_node is None:
                    continue

                for superclass_node in superclasses_node.named_children:
                    superclass_name = self._get_superclass_name(
                        superclass_node,
                        source_code,
                    )

                    if superclass_name is None:
                        continue

                    target_class = self._resolve_base_class(
                        superclass_name,
                        source_class,
                        classes_by_name,
                    )

                    if target_class is None:
                        continue

                    relationship_key = (
                        source_class.entity_id,
                        target_class.entity_id,
                    )

                    if relationship_key in seen_relationships:
                        continue

                    seen_relationships.add(relationship_key)

                    relationships.append(
                        CodeRelationship(
                            source_entity_id=source_class.entity_id,
                            target_entity_id=target_class.entity_id,
                            relationship_type=RelationshipType.INHERITS,
                        )
                    )

        return relationships

    @staticmethod
    def _walk_class_definitions(node):
        """Yield all class definition nodes in a syntax tree."""
        if node.type == "class_definition":
            yield node

        for child in node.named_children:
            yield from RelationshipExtractor._walk_class_definitions(
                child,
            )

    @staticmethod
    def _get_node_text(
        node,
        source_code: str,
    ) -> str | None:
        """Return the source text represented by a Tree-sitter node."""
        if node is None:
            return None

        source_bytes = source_code.encode("utf-8")

        return source_bytes[
            node.start_byte:node.end_byte
        ].decode("utf-8")

    @staticmethod
    def _get_superclass_name(
        node,
        source_code: str,
    ) -> str | None:
        """
        Extract a superclass name from a superclass expression.

        For simple names such as ``AuthService``, the full name is returned.
        For qualified names such as ``base.AuthService``, the final class
        component is used.
        """
        text = RelationshipExtractor._get_node_text(
            node,
            source_code,
        )

        if text is None:
            return None

        text = text.strip()

        if not text:
            return None

        return text.split(".")[-1]

    @staticmethod
    def _find_class_entity(
        classes: list[CodeEntity],
        class_name: str,
    ) -> CodeEntity | None:
        """Find a class entity by name within a file."""
        for class_entity in classes:
            if class_entity.name == class_name:
                return class_entity

        return None

    @staticmethod
    def _resolve_base_class(
        superclass_name: str,
        source_class: CodeEntity,
        classes_by_name: dict[str, list[CodeEntity]],
    ) -> CodeEntity | None:
        """
        Resolve a superclass name to a class entity.

        Same-file classes are preferred. If no same-file class exists,
        a repository-wide unique class name may be used.
        """
        candidates = classes_by_name.get(
            superclass_name,
            [],
        )

        if not candidates:
            return None

        same_file_candidates = [
            candidate
            for candidate in candidates
            if candidate.file == source_class.file
        ]

        if len(same_file_candidates) == 1:
            return same_file_candidates[0]

        if len(candidates) == 1:
            return candidates[0]

        return None

    @staticmethod
    def _resolve_import_paths(
        import_statement: str,
        source_file: str,
        files_by_path: dict[str, CodeEntity],
    ) -> list[str]:
        """Resolve an import statement to repository-local Python files."""
        statement = import_statement.strip()

        if statement.startswith("from "):
            module_part = statement[5:].split(
                " import ",
                1,
            )[0].strip()

        elif statement.startswith("import "):
            module_part = statement[7:].strip().split(
                ",",
                1,
            )[0].strip()

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
        module_path = module_part.replace(
            ".",
            "/",
        )

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
            target_directory /= remainder.replace(
                ".",
                "/",
            )

        candidates = [
            f"{target_directory.as_posix()}.py",
            f"{target_directory.as_posix()}/__init__.py",
        ]

        return [
            candidate
            for candidate in candidates
            if candidate in files_by_path
        ]
