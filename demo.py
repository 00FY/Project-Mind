"""ProjectMind Mid-Semester Demonstration Script."""

import sys
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

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
            "[bold cyan]ProjectMind Mid-Semester Architecture Demo[/bold cyan]\n"
            "[dim]Integrating Member 1 (CI) + Member 2 (Memory) + Member 3 (Retrieval)[/dim]",
            border_style="cyan",
        )
    )

    # ----------------------------------------------------
    # 1. Initialize Member 1 (Code Intelligence)
    # ----------------------------------------------------
    console.print("\n[bold yellow]1. Initializing Member 1 (Code Intelligence)...[/bold yellow]")
    ci_service = CodeIntelligenceService(project_root)
    result = ci_service.index_project(str(project_root))
    console.print(f"  [green][OK][/green] Indexed [bold]{result.files_indexed}[/bold] files in {result.duration_seconds:.2f}s")

    # ----------------------------------------------------
    # 2. Initialize Member 2 (Project Memory)
    # ----------------------------------------------------
    console.print("\n[bold yellow]2. Initializing Member 2 (Project Memory)...[/bold yellow]")
    db_path = project_root / ".projectmind" / "demo_memory.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    repo = MemoryRepository(db_path)
    now = utc_now()

    # Create evidence
    repo.create_evidence(
        Evidence(
            id="ev-001",
            kind=EvidenceKind.CODE,
            file_path="projectmind/platform/mcp/server.py",
            description="MCP Server implementation",
        )
    )

    # Seed sample memories
    memories = [
        Memory(
            id="mem-001",
            type=MemoryType.GOAL,
            content="Provide local-first, model-independent project intelligence for AI coding agents.",
            importance=0.9,
            confidence=1.0,
            created_at=now,
            updated_at=now,
            evidence=["ev-001"],
        ),
        Memory(
            id="mem-002",
            type=MemoryType.ARCHITECTURE,
            content="ProjectMind uses a 3-tier architecture: Code Intelligence (M1), Project Memory (M2), Context Retrieval (M3).",
            importance=0.95,
            confidence=1.0,
            created_at=now,
            updated_at=now,
            evidence=["ev-001"],
        ),
        Memory(
            id="mem-003",
            type=MemoryType.CONSTRAINT,
            content="All memory database operations must use parameterized SQLite transactions to ensure thread safety.",
            importance=0.85,
            confidence=0.9,
            created_at=now,
            updated_at=now,
            evidence=["ev-001"],
        ),
    ]

    for m in memories:
        repo.create_memory(m)

    memory_service = SQLiteProjectMemory(repo)
    status = memory_service.get_status()
    console.print(f"  [green][OK][/green] Memory Store online ([bold]{status.total_items}[/bold] items stored in SQLite)")

    # ----------------------------------------------------
    # 3. Initialize Member 3 (Context & Retrieval)
    # ----------------------------------------------------
    console.print("\n[bold yellow]3. Initializing Member 3 (Context & Retrieval)...[/bold yellow]")
    retrieval_service = RetrievalService(
        code_intelligence=ci_service,
        project_memory=memory_service,
    )
    console.print("  [green][OK][/green] BM25 Retriever & Utility-per-token Budget Controller online")

    # ----------------------------------------------------
    # 4. Wire everything into ProjectMindCore
    # ----------------------------------------------------
    core = ProjectMindCore(
        code_intelligence=ci_service,
        project_memory=memory_service,
        context_retriever=retrieval_service,
    )
    console.print(f"\n[bold green][OK] ProjectMindCore fully configured: {core.is_fully_configured()}[/bold green]\n")

    # ----------------------------------------------------
    # 5. Execute Context Retrieval Task
    # ----------------------------------------------------
    task_query = "How does database memory persistence work in ProjectMind?"
    console.print(Panel(f"[bold white]Query Task:[/bold white] {task_query}", border_style="blue"))

    context = core.context_retriever.get_context(
        task=task_query,
        token_budget=2000,
        include_code=True,
    )

    # ----------------------------------------------------
    # 6. Display Results
    # ----------------------------------------------------
    # Knowledge Table
    table_k = Table(title="Retrieved Knowledge Items (Member 2)")
    table_k.add_column("Category", style="cyan")
    table_k.add_column("Title / Content", style="white")
    table_k.add_column("Relevance", style="green")

    for k in context.knowledge_items:
        table_k.add_row(k.category, k.content, f"{k.relevance_score:.2f}")

    console.print(table_k)

    # Code Chunks Table
    table_c = Table(title="Retrieved Code Chunks (Member 1)")
    table_c.add_column("File Path", style="cyan")
    table_c.add_column("Lines", style="yellow")
    table_c.add_column("Summary", style="white")

    for c in context.code_chunks:
        table_c.add_row(c.file_path, f"L{c.start_line}-L{c.end_line}", c.summary or "Code Snippet")

    console.print(table_c)

    # Warnings & Budget Summary
    if context.warnings:
        console.print("\n[bold red]Triggered Warnings:[/bold red]")
        for w in context.warnings:
            console.print(f"  • [[bold]{w.severity.upper()}[/bold]] {w.category}: {w.message}")

    console.print(
        Panel(
            f"[bold]Token Budget Usage:[/bold] {context.token_count} / {context.token_budget} tokens\n"
            f"[dim]{context.retrieval_notes}[/dim]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    run_demo()
