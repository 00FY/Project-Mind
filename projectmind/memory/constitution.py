from pydantic import BaseModel, ConfigDict, Field


class ProjectConstitution(BaseModel):
    """
    Defines the high-level, relatively stable knowledge
    that describes a ProjectMind project.

    The constitution provides project context such as:
    - project goal
    - requirements
    - architecture
    - constraints
    - decisions
    - non-goals
    """

    model_config = ConfigDict(extra="forbid")

    goal: str = Field(
        min_length=1,
        description="Primary goal of the project."
    )

    requirements: list[str] = Field(
        default_factory=list,
        description="Functional and technical requirements."
    )

    architecture: list[str] = Field(
        default_factory=list,
        description="High-level architectural components and structure."
    )

    constraints: list[str] = Field(
        default_factory=list,
        description="Known project constraints and limitations."
    )

    decisions: list[str] = Field(
        default_factory=list,
        description="Important architectural or technical decisions."
    )

    non_goals: list[str] = Field(
        default_factory=list,
        description="Things explicitly outside the project's scope."
    )