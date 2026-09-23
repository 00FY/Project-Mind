"""Tests for the ProjectMind code indexer."""

from pathlib import Path

from projectmind.code_intelligence.indexer import CodeIndexer


def create_file(path: Path, content: str) -> None:
    """Create a file and any required parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_indexer_extracts_python_entities(tmp_path: Path) -> None:
    """The indexer should extract entities from Python source files."""
    create_file(
        tmp_path / "auth.py",
        """class AuthService:
    def login(self):
        return True
""",
    )

    indexer = CodeIndexer(tmp_path)

    entities = indexer.index()

    entity_types = {
        entity.type.value
        for entity in entities
    }

    assert "file" in entity_types
    assert "class" in entity_types
    assert "method" in entity_types

    auth_class = next(
        entity
        for entity in entities
        if entity.type.value == "class"
        and entity.name == "AuthService"
    )

    login_method = next(
        entity
        for entity in entities
        if entity.type.value == "method"
        and entity.name == "login"
    )

    assert auth_class.file == "auth.py"
    assert login_method.file == "auth.py"


def test_indexer_extracts_relationships(tmp_path: Path) -> None:
    """The indexer should extract relationships between code entities."""
    create_file(
        tmp_path / "auth.py",
        """class AuthService:
    def login(self):
        return True
""",
    )

    indexer = CodeIndexer(tmp_path)

    entities = indexer.index()

    assert len(entities) == 3
    assert len(indexer.relationships) == 1

    relationship = indexer.relationships[0]

    assert relationship.relationship_type.value == "contains"

    class_entity = next(
        entity
        for entity in entities
        if entity.type.value == "class"
        and entity.name == "AuthService"
    )

    method_entity = next(
        entity
        for entity in entities
        if entity.type.value == "method"
        and entity.name == "login"
    )

    assert relationship.source_entity_id == class_entity.entity_id
    assert relationship.target_entity_id == method_entity.entity_id


def test_indexer_extracts_inheritance_relationship(
    tmp_path: Path,
) -> None:
    """The indexer should detect inheritance between classes."""
    create_file(
        tmp_path / "auth.py",
        """class AuthService:
    pass


class AdminService(AuthService):
    pass
""",
    )

    indexer = CodeIndexer(tmp_path)

    entities = indexer.index()

    auth_class = next(
        entity
        for entity in entities
        if entity.type.value == "class"
        and entity.name == "AuthService"
    )

    admin_class = next(
        entity
        for entity in entities
        if entity.type.value == "class"
        and entity.name == "AdminService"
    )

    inheritance_relationships = [
        relationship
        for relationship in indexer.relationships
        if relationship.relationship_type.value == "inherits"
    ]

    assert len(inheritance_relationships) == 1

    relationship = inheritance_relationships[0]

    assert relationship.source_entity_id == admin_class.entity_id
    assert relationship.target_entity_id == auth_class.entity_id
