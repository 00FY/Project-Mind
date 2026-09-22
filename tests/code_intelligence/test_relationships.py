"""Tests for code relationship extraction."""

from projectmind.code_intelligence.entities import PythonEntityExtractor
from projectmind.code_intelligence.models import RelationshipType
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
