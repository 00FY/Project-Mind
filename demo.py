"""ProjectMind Architecture Jury Demo.

ProjectMind (the AI project intelligence engine) analyzes an external
demonstration software project: TaskFlow API.
"""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Target demonstration repository analyzed by ProjectMind
demo_repo = project_root / "taskflow-api"

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from projectmind.code_intelligence.service import CodeIntelligenceService
from projectmind.core.interfaces import ProjectMindCore
from projectmind.memory.enums import MemoryType
from projectmind.memory.evidence import Evidence, EvidenceKind
from projectmind.memory.models import Memory, utc_now
from projectmind.memory.project_memory import SQLiteProjectMemory
from projectmind.memory.repository import MemoryRepository
from projectmind.retrieval.service import RetrievalService

console = Console()


def run_demo():
    console.print(
        Panel.fit(
            "[bold cyan]ProjectMind AI Agent Demonstration[/bold cyan]\n"
            "[bold white]Engine:[/bold white] ProjectMind System (M1 + M2 + M3)\n"
            "[bold white]Analyzed Project:[/bold white] TaskFlow API ([dim]taskflow-api/[/dim])",
            border_style="cyan",
        )
    )

    # ----------------------------------------------------
    # 1. Initialize Member 1 (Code Intelligence) on TaskFlow API
    # ----------------------------------------------------
    console.print("\n[bold yellow]1. [Member 1] Code Intelligence scanning TaskFlow API codebase...[/bold yellow]")
    ci_service = CodeIntelligenceService(demo_repo)
    result = ci_service.index_project(str(demo_repo))
    console.print(f"  [green][OK][/green] Scanned & Indexed [bold]{result.files_indexed}[/bold] source files in TaskFlow API")

    # ----------------------------------------------------
    # 2. Initialize Member 2 (Project Memory) for TaskFlow API
    # ----------------------------------------------------
    console.print("\n[bold yellow]2. [Member 2] Loading Project Memory store for TaskFlow API...[/bold yellow]")
    db_path = project_root / ".projectmind" / "taskflow_memory.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    repo = MemoryRepository(db_path)
    now = utc_now()

    # Create evidence linked to TaskFlow API code files
    repo.create_evidence(
        Evidence(
            id="ev-auth-01",
            kind=EvidenceKind.CODE,
            file_path="src/auth/service.py",
            description="TaskFlow API Auth implementation",
        )
    )
    repo.create_evidence(
        Evidence(
            id="ev-db-01",
            kind=EvidenceKind.CODE,
            file_path="src/database/connection.py",
            description="TaskFlow API Database Manager",
        )
    )

    # Seed project-level memory records for TaskFlow API
    memories = [
        Memory(
            id="mem-001",
            type=MemoryType.GOAL,
            content="Provide a secure RESTful Task Management API microservice.",
            importance=0.9,
            confidence=1.0,
            created_at=now,
            updated_at=now,
            evidence=["ev-auth-01"],
        ),
        Memory(
            id="mem-002",
            type=MemoryType.ARCHITECTURE,
            content="TaskFlow API uses a 3-layer architecture: APIRouter -> Services (AuthService, TaskService) -> DatabaseManager.",
            importance=0.95,
            confidence=1.0,
            created_at=now,
            updated_at=now,
            evidence=["ev-auth-01"],
        ),
        Memory(
            id="mem-003",
            type=MemoryType.CONSTRAINT,
            content="All database queries in TaskFlow API must use parameterized SQLite statements to prevent SQL injection.",
            importance=0.9,
            confidence=0.95,
            created_at=now,
            updated_at=now,
            evidence=["ev-db-01"],
        ),
        Memory(
            id="mem-004",
            type=MemoryType.DECISION,
            content="Session authentication uses JWT tokens stored in UserSession dict.",
            importance=0.85,
            confidence=0.9,
            created_at=now,
            updated_at=now,
            evidence=["ev-auth-01"],
        ),
    ]

    for m in memories:
        repo.create_memory(m)

    memory_service = SQLiteProjectMemory(repo)
    status = memory_service.get_status()
    console.print(f"  [green][OK][/green] Project Memory online ([bold]{status.total_items}[/bold] memories stored in SQLite)")

    # ----------------------------------------------------
    # 3. Initialize Member 3 (Context & Retrieval)
    # ----------------------------------------------------
    console.print("\n[bold yellow]3. [Member 3] Initializing Context Retrieval & Token Budget Controller...[/bold yellow]")
    retrieval_service = RetrievalService(
        code_intelligence=ci_service,
        project_memory=memory_service,
    )
    console.print("  [green][OK][/green] BM25 Search & Utility-per-token Budget Controller online")

    # ----------------------------------------------------
    # 4. Wire into ProjectMindCore
    # ----------------------------------------------------
    core = ProjectMindCore(
        code_intelligence=ci_service,
        project_memory=memory_service,
        context_retriever=retrieval_service,
    )
    console.print(f"\n[bold green][OK] ProjectMindCore active for TaskFlow API: {core.is_fully_configured()}[/bold green]\n")

    # ----------------------------------------------------
    # 5. Developer Task Request
    # ----------------------------------------------------
    developer_task = "Add OAuth authentication and session token verification to TaskFlow API"
    console.print(Panel(f"[bold white]Developer Task Request:[/bold white]\n[cyan]\"{developer_task}\"[/cyan]", border_style="blue"))

    context = core.context_retriever.get_context(
        task=developer_task,
        token_budget=2000,
        include_code=True,
    )

    # ----------------------------------------------------
    # 6. Display Results
    # ----------------------------------------------------
    # Knowledge Table
    table_k = Table(title="Retrieved Project Memories (Member 2)")
    table_k.add_column("Category", style="cyan")
    table_k.add_column("Content / Memory", style="white")
    table_k.add_column("Relevance", style="green")

    for k in context.knowledge_items:
        table_k.add_row(k.category, k.content, f"{k.relevance_score:.2f}")

    console.print(table_k)

    # Code Chunks Table
    table_c = Table(title="Retrieved Code Entities from TaskFlow API (Member 1)")
    table_c.add_column("File Path", style="cyan")
    table_c.add_column("Lines", style="yellow")
    table_c.add_column("Summary", style="white")

    for c in context.code_chunks:
        table_c.add_row(c.file_path, f"L{c.start_line}-L{c.end_line}", c.summary or "Code Snippet")

    console.print(table_c)

    # Warnings & Budget Summary
    if context.warnings:
        console.print("\n[bold red]Triggered Security & Architecture Constraints:[/bold red]")
        for w in context.warnings:
            console.print(f"  • [[bold]{w.severity.upper()}[/bold]] {w.category}: {w.message}")

    console.print(
        Panel(
            f"[bold]Context Package Token Usage:[/bold] {context.token_count} / {context.token_budget} tokens\n"
            f"[dim]{context.retrieval_notes}[/dim]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    run_demo()
