"""Tree-sitter based source code parsing for ProjectMind."""

import tree_sitter_python as tspython
from tree_sitter import Language, Parser, Tree


class PythonParser:
    """Parse Python source code using Tree-sitter."""

    def __init__(self) -> None:
        python_language = Language(tspython.language())
        self.parser = Parser(python_language)

    def parse(self, source_code: str) -> Tree:
        """Parse Python source code and return the syntax tree."""
        source_bytes = source_code.encode("utf-8")
        return self.parser.parse(source_bytes)
