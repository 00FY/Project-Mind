"""Tests for the ProjectMind repository scanner."""

from pathlib import Path

from projectmind.code_intelligence.scanner import RepositoryScanner


def create_file(path: Path, content: str = "") -> None:
    """Create a file and any missing parent directories."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_scanner_finds_supported_source_files(tmp_path: Path) -> None:
    """Scanner should discover supported source files."""
    create_file(tmp_path / "src" / "auth.py", "def login():\n    pass\n")
    create_file(tmp_path / "src" / "app.js", "function main() {}\n")
    create_file(tmp_path / "README.md", "# Demo Project\n")

    scanner = RepositoryScanner(tmp_path)
    files = scanner.scan()

    paths = {file.path for file in files}

    assert "src/auth.py" in paths
    assert "src/app.js" in paths
    assert "README.md" not in paths


def test_scanner_detects_languages(tmp_path: Path) -> None:
    """Scanner should assign the correct language from file extensions."""
    create_file(tmp_path / "main.py", "print('hello')\n")
    create_file(tmp_path / "app.js", "console.log('hello');\n")
    create_file(tmp_path / "main.ts", "console.log('hello');\n")

    scanner = RepositoryScanner(tmp_path)
    files = scanner.scan()

    languages = {file.path: file.language for file in files}

    assert languages["main.py"] == "python"
    assert languages["app.js"] == "javascript"
    assert languages["main.ts"] == "typescript"


def test_scanner_ignores_excluded_directories(tmp_path: Path) -> None:
    """Scanner should ignore configured directories."""
    create_file(tmp_path / "src" / "main.py", "print('hello')\n")
    create_file(tmp_path / ".git" / "config.py", "ignored = True\n")
    create_file(tmp_path / ".venv" / "Scripts" / "fake.py", "ignored = True\n")
    create_file(tmp_path / "__pycache__" / "fake.py", "ignored = True\n")
    create_file(tmp_path / "node_modules" / "package.py", "ignored = True\n")

    scanner = RepositoryScanner(tmp_path)
    files = scanner.scan()

    paths = {file.path for file in files}

    assert "src/main.py" in paths
    assert ".git/config.py" not in paths
    assert ".venv/Scripts/fake.py" not in paths
    assert "__pycache__/fake.py" not in paths
    assert "node_modules/package.py" not in paths


def test_scanned_file_contains_file_size(tmp_path: Path) -> None:
    """Scanner should record the size of each discovered file."""
    content = "print('hello')\n"
    file_path = tmp_path / "main.py"
    create_file(file_path, content)

    scanner = RepositoryScanner(tmp_path)
    files = scanner.scan()

    assert len(files) == 1
    assert files[0].path == "main.py"
    assert files[0].size_bytes == file_path.stat().st_size
