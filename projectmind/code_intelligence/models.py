"""Data models for ProjectMind code intelligence."""

from enum import StrEnum

from pydantic import BaseModel, Field


class EntityType(StrEnum):
    """Types of code entities recognized by ProjectMind."""

    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    IMPORT = "import"


class CodeEntity(BaseModel):
    """
    A structured representation of an entity found in the codebase.

    Paths are stored relative to the repository root.
    """

    entity_id: str = Field(min_length=1)
    type: EntityType
    name: str = Field(min_length=1)
    file: str = Field(min_length=1)
    line_start: int = Field(ge=1)
    line_end: int = Field(ge=1)
    language: str = Field(default="python", min_length=1)
