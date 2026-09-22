"""Tests for the ProjectMind Tree-sitter parser."""

from projectmind.code_intelligence.parser import PythonParser


def test_parser_creates_syntax_tree() -> None:
    """Parser should create a syntax tree for valid Python."""
    source = """
class AuthService:
    def login(self):
        return True
"""

    tree = PythonParser().parse(source)

    assert tree.root_node.type == "module"
    assert len(tree.root_node.children) == 1


def test_parser_detects_class() -> None:
    """Parser should recognize a Python class."""
    source = """
class AuthService:
    pass
"""

    tree = PythonParser().parse(source)

    class_node = tree.root_node.children[0]

    assert class_node.type == "class_definition"


def test_parser_detects_function() -> None:
    """Parser should recognize a Python function."""
    source = """
def login(username):
    return True
"""

    tree = PythonParser().parse(source)

    function_node = tree.root_node.children[0]

    assert function_node.type == "function_definition"


def test_parser_handles_empty_source() -> None:
    """Parser should handle an empty source file."""
    tree = PythonParser().parse("")

    assert tree.root_node.type == "module"
