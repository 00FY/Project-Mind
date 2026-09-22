"""Tests for ProjectMind Python entity extraction."""

from projectmind.code_intelligence.entities import PythonEntityExtractor


def test_extracts_class() -> None:
    """Extractor should identify Python classes."""
    source = """class AuthService:
    pass
"""

    entities = PythonEntityExtractor().extract(
        source,
        "src/auth.py",
    )

    assert len(entities) == 1
    assert entities[0].type == "class"
    assert entities[0].name == "AuthService"
    assert entities[0].file == "src/auth.py"
    assert entities[0].line_start == 1
    assert entities[0].line_end == 2


def test_extracts_function() -> None:
    """Extractor should identify top-level functions."""
    source = """def validate_token(token):
    return True
"""

    entities = PythonEntityExtractor().extract(
        source,
        "src/auth.py",
    )

    assert len(entities) == 1
    assert entities[0].type == "function"
    assert entities[0].name == "validate_token"


def test_extracts_method() -> None:
    """Extractor should distinguish methods from top-level functions."""
    source = """class AuthService:
    def login(self):
        return True
"""

    entities = PythonEntityExtractor().extract(
        source,
        "src/auth.py",
    )

    assert len(entities) == 2

    assert entities[0].type == "class"
    assert entities[0].name == "AuthService"

    assert entities[1].type == "method"
    assert entities[1].name == "login"


def test_extracts_import() -> None:
    """Extractor should identify import statements."""
    source = """import sqlite3
from pathlib import Path
"""

    entities = PythonEntityExtractor().extract(
        source,
        "src/database.py",
    )

    assert len(entities) == 2
    assert entities[0].type == "import"
    assert entities[1].type == "import"


def test_entity_ids_are_deterministic() -> None:
    """The same source should produce the same entity IDs."""
    source = """class AuthService:
    pass
"""

    extractor = PythonEntityExtractor()

    first = extractor.extract(source, "src/auth.py")
    second = extractor.extract(source, "src/auth.py")

    assert first[0].entity_id == second[0].entity_id


def test_extracts_multiple_entity_types() -> None:
    """Extractor should identify different entity types in one file."""
    source = """import sqlite3

class UserService:
    def create_user(self):
        pass

def validate_user(user):
    return True
"""

    entities = PythonEntityExtractor().extract(
        source,
        "src/user.py",
    )

    entity_types = [(entity.type, entity.name) for entity in entities]

    assert ("import", "import sqlite3") in entity_types
    assert ("class", "UserService") in entity_types
    assert ("method", "create_user") in entity_types
    assert ("function", "validate_user") in entity_types
