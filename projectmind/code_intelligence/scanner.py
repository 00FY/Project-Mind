"""Repository scanning for ProjectMind code intelligence."""

from pathlib import Path

from projectmind.code_intelligence.models import ScannedFile
from projectmind.platform.config.settings import get_settings


class RepositoryScanner:
    """Discover source files in a ProjectMind project."""

    LANGUAGE_MAP = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".go": "go",
        ".cpp": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
    }

    def __init__(self, project_root: str | Path | None = None):
        settings = get_settings()

        self.project_root = (
            Path(project_root).resolve() if project_root is not None else settings.project.root
        )

        self.exclude_patterns = settings.project.exclude_patterns

    def scan(self) -> list[ScannedFile]:
        """Scan the project and return discovered source files."""
        scanned_files: list[ScannedFile] = []

        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue

            if self._is_excluded(path):
                continue

            language = self._detect_language(path)

            if language is None:
                continue

            relative_path = path.relative_to(self.project_root)

            scanned_files.append(
                ScannedFile(
                    path=relative_path.as_posix(),
                    language=language,
                    size_bytes=path.stat().st_size,
                )
            )

        return scanned_files

    def _is_excluded(self, path: Path) -> bool:
        """Return True when a path matches the configured exclusions."""
        relative_path = path.relative_to(self.project_root).as_posix()

        return any(
            self._matches_pattern(relative_path, pattern) for pattern in self.exclude_patterns
        )

    @staticmethod
    def _matches_pattern(path: str, pattern: str) -> bool:
        """Match a repository-relative path against an exclusion pattern."""
        normalized_pattern = pattern.replace("**/", "")

        if normalized_pattern.endswith("/**"):
            directory = normalized_pattern[:-3].rstrip("/")
            return path == directory or path.startswith(f"{directory}/")

        return Path(path).match(pattern) or Path(path).match(normalized_pattern)

    @classmethod
    def _detect_language(cls, path: Path) -> str | None:
        """Return the language associated with a file extension."""
        return cls.LANGUAGE_MAP.get(path.suffix.lower())
