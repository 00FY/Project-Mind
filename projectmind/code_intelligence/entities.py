"""Extract structured code entities from Tree-sitter syntax trees."""

from hashlib import sha1

from tree_sitter import Node

from projectmind.code_intelligence.models import CodeEntity, EntityType
from projectmind.code_intelligence.parser import PythonParser


class PythonEntityExtractor:
    """Extract classes, functions, methods, and imports from Python code."""

    def __init__(self) -> None:
        self.parser = PythonParser()

    def extract(
        self,
        source_code: str,
        file_path: str,
    ) -> list[CodeEntity]:
        """
        Parse Python source code and extract structured code entities.

        Args:
            source_code: Python source code.
            file_path: Repository-relative path to the source file.

        Returns:
            A list of CodeEntity objects.
        """
        tree = self.parser.parse(source_code)
        entities: list[CodeEntity] = []

        self._walk(
            node=tree.root_node,
            source_bytes=source_code.encode("utf-8"),
            file_path=file_path,
            entities=entities,
            inside_class=False,
        )

        return entities

    def _walk(
        self,
        node: Node,
        source_bytes: bytes,
        file_path: str,
        entities: list[CodeEntity],
        inside_class: bool,
    ) -> None:
        """Walk the syntax tree and collect recognized entities."""

        node_type = node.type

        if node_type == "class_definition":
            name = self._get_node_name(node, source_bytes)

            if name:
                entities.append(
                    self._create_entity(
                        node=node,
                        entity_type=EntityType.CLASS,
                        name=name,
                        file_path=file_path,
                    )
                )

            for child in node.children:
                self._walk(
                    node=child,
                    source_bytes=source_bytes,
                    file_path=file_path,
                    entities=entities,
                    inside_class=True,
                )

            return

        if node_type == "function_definition":
            name = self._get_node_name(node, source_bytes)

            if name:
                entity_type = (
                    EntityType.METHOD
                    if inside_class
                    else EntityType.FUNCTION
                )

                entities.append(
                    self._create_entity(
                        node=node,
                        entity_type=entity_type,
                        name=name,
                        file_path=file_path,
                    )
                )

        elif node_type in {"import_statement", "import_from_statement"}:
            name = source_bytes[
                node.start_byte:node.end_byte
            ].decode("utf-8")

            entities.append(
                self._create_entity(
                    node=node,
                    entity_type=EntityType.IMPORT,
                    name=name,
                    file_path=file_path,
                )
            )

        for child in node.children:
            self._walk(
                node=child,
                source_bytes=source_bytes,
                file_path=file_path,
                entities=entities,
                inside_class=inside_class,
            )

    @staticmethod
    def _get_node_name(
        node: Node,
        source_bytes: bytes,
    ) -> str | None:
        """Extract the name field from a Tree-sitter node."""
        name_node = node.child_by_field_name("name")

        if name_node is None:
            return None

        return source_bytes[
            name_node.start_byte:name_node.end_byte
        ].decode("utf-8")

    @staticmethod
    def _create_entity(
        node: Node,
        entity_type: EntityType,
        name: str,
        file_path: str,
    ) -> CodeEntity:
        """Create a deterministic CodeEntity from a Tree-sitter node."""

        raw_id = f"{file_path}:{entity_type.value}:{name}:{node.start_byte}"

        entity_id = sha1(
            raw_id.encode("utf-8")
        ).hexdigest()[:12]

        return CodeEntity(
            entity_id=entity_id,
            type=entity_type,
            name=name,
            file=file_path,
            line_start=node.start_point[0] + 1,
            line_end=node.end_point[0] + 1,
            language="python",
        )
