"""Tests for code relationship extraction."""

from projectmind.code_intelligence.entities import PythonEntityExtractor
from projectmind.code_intelligence.models import (
    CodeEntity,
    EntityType,
    RelationshipType,
)
from projectmind.code_intelligence.relationships import RelationshipExtractor


def test_extract_class_contains_method() -> None:
    source = """class AuthService:
    def login(self):
        return True

    def logout(self):
        return False
"""

    extractor = PythonEntityExtractor()
    entities = extractor.extract(source, "auth.py")

    relationship_extractor = RelationshipExtractor()
    relationships = relationship_extractor.extract(entities)

    assert len(relationships) == 2

    relationship_types = {
        relationship.relationship_type
        for relationship in relationships
    }

    assert relationship_types == {RelationshipType.CONTAINS}


def test_extract_local_import_relationship() -> None:
    entities = [
        CodeEntity(
            entity_id="auth-file",
            type=EntityType.FILE,
            name="auth",
            file="auth.py",
            line_start=1,
            line_end=10,
            language="python",
        ),
        CodeEntity(
            entity_id="database-file",
            type=EntityType.FILE,
            name="database",
            file="database.py",
            line_start=1,
            line_end=10,
            language="python",
        ),
        CodeEntity(
            entity_id="import-1",
            type=EntityType.IMPORT,
            name="from database import Database",
            file="auth.py",
            line_start=1,
            line_end=1,
            language="python",
        ),
    ]

    extractor = RelationshipExtractor()

    relationships = extractor.extract(entities)

    import_relationships = [
        relationship
        for relationship in relationships
        if relationship.relationship_type
        == RelationshipType.IMPORTS
    ]

    assert len(import_relationships) == 1

    relationship = import_relationships[0]

    assert relationship.source_entity_id == "auth-file"
    assert relationship.target_entity_id == "database-file"


def test_import_relationships_are_unique() -> None:
    entities = [
        CodeEntity(
            entity_id="auth-file",
            type=EntityType.FILE,
            name="auth",
            file="auth.py",
            line_start=1,
            line_end=10,
            language="python",
        ),
        CodeEntity(
            entity_id="database-file",
            type=EntityType.FILE,
            name="database",
            file="database.py",
            line_start=1,
            line_end=10,
            language="python",
        ),
        CodeEntity(
            entity_id="import-1",
            type=EntityType.IMPORT,
            name="from database import Database",
            file="auth.py",
            line_start=1,
            line_end=1,
            language="python",
        ),
        CodeEntity(
            entity_id="import-2",
            type=EntityType.IMPORT,
            name="from database import Connection",
            file="auth.py",
            line_start=2,
            line_end=2,
            language="python",
        ),
    ]

    extractor = RelationshipExtractor()

    relationships = extractor.extract(entities)

    import_relationships = [
        relationship
        for relationship in relationships
        if relationship.relationship_type
        == RelationshipType.IMPORTS
    ]

    assert len(import_relationships) == 1
    assert import_relationships[0].source_entity_id == "auth-file"
    assert import_relationships[0].target_entity_id == "database-file"
