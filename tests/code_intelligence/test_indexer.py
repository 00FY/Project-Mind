"""Tests for the ProjectMind code indexing pipeline."""

from pathlib import Path

from projectmind.code_intelligence.indexer import CodeIndexer


def create_file(path: Path, content: str) -> None:
    """Create a test source file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_indexer_extracts_entities_from_python_files(
    tmp_path: Path,
) -> None:
    """Indexer should scan Python files and extract their entities."""
    create_file(
        tmp_path / "src" / "auth.py",
        """import sqlite3

class AuthService:
    def login(self):
        return True

def validate_token(token):
    return True
""",
    )

    indexer = CodeIndexer(tmp_path)
    entities = indexer.index()

    entity_types = [
        (entity.type, entity.name)
        for entity in entities
    ]

    assert ("import", "import sqlite3") in entity_types
    assert ("class", "AuthService") in entity_types
    assert ("method", "login") in entity_types
    assert ("function", "validate_token") in entity_types


def test_indexer_ignores_unsupported_languages(
    tmp_path: Path,
) -> None:
    """Indexer should not try to parse unsupported languages yet."""
    create_file(
        tmp_path / "src" / "app.js",
        "function main() {}\n",
    )

    indexer = CodeIndexer(tmp_path)
    entities = indexer.index()

    assert entities == []


def test_indexer_extracts_relationships(tmp_path: Path) -> None:
    source = """class AuthService:
    def login(self):
        return True
"""

    file_path = tmp_path / "auth.py"
    file_path.write_text(source, encoding="utf-8")

    indexer = CodeIndexer(tmp_path)

    entities = indexer.index()

    assert len(entities) == 2
    assert len(indexer.relationships) == 1

    relationship = indexer.relationships[0]

    assert relationship.relationship_type.value == "contains"

    class_entity = next(
        entity for entity in entities
        if entity.type.value == "class"
    )

    method_entity = next(
        entity for entity in entities
        if entity.type.value == "method"
    )

    assert relationship.source_entity_id == class_entity.entity_id
    assert relationship.target_entity_id == method_entity.entity_id
