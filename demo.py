"""ProjectMind Dynamic Demo.

Usage:
    python demo.py                          # uses built-in taskflow-api/ demo project
    python demo.py <path-to-any-project>    # scans any project folder
    python demo.py <path> --task "your task description here"

Examples:
    python demo.py
    python demo.py D:\\Desktop\\Final_AetherDock_G9
    python demo.py D:\\Desktop\\Final_AetherDock_G9 --task "Add user authentication module"
"""

import sys
import argparse
from pathlib import Path

# Add project root to sys.path so projectmind package is always found
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from projectmind.code_intelligence.service import CodeIntelligenceService
from projectmind.core.interfaces import ProjectMindCore
from projectmind.memory.enums import MemoryType
from projectmind.memory.evidence import Evidence, EvidenceKind
from projectmind.memory.models import Memory, utc_now
from projectmind.memory.project_memory import SQLiteProjectMemory
from projectmind.memory.repository import MemoryRepository
from projectmind.retrieval.service import RetrievalService

console = Console()


def parse_args():
    parser = argparse.ArgumentParser(
        description="ProjectMind Dynamic Demo — analyze any project folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "project_path",
        nargs="?",
        default=None,
        help="Path to the project folder to analyze. Defaults to built-in taskflow-api/.",
    )
    parser.add_argument(
        "--task",
        default=None,
        help="Developer task description to retrieve context for. If not given, you will be prompted.",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=2000,
        help="Token budget for context retrieval (default: 2000).",
    )
    return parser.parse_args()


def run_demo(target_path: Path, developer_task: str, token_budget: int):
    project_name = target_path.name

    console.print(
        Panel.fit(
            f"[bold cyan]ProjectMind AI Agent Demonstration[/bold cyan]\n"
            f"[bold white]Engine:[/bold white] ProjectMind System (M1 + M2 + M3)\n"
            f"[bold white]Analyzing Project:[/bold white] [green]{project_name}[/green] "
            f"([dim]{target_path}[/dim])",
            border_style="cyan",
        )
    )

    # ------------------------------------------------------------------
    # 1. Member 1 — Code Intelligence: scan & index the target project
    # ------------------------------------------------------------------
    console.print(f"\n[bold yellow]1. [Member 1] Code Intelligence scanning {project_name} codebase...[/bold yellow]")
    ci_service = CodeIntelligenceService(target_path)
    result = ci_service.index_project(str(target_path))
    console.print(
        f"  [green][OK][/green] Scanned & Indexed [bold]{result.files_indexed}[/bold] "
        f"source files in {project_name}"
    )

    if result.files_indexed == 0:
        console.print(
            "  [yellow][WARN][/yellow] No Python files found in this folder. "
            "Code Intelligence table will be empty — memory demo will still work."
        )

    # ------------------------------------------------------------------
    # 2. Member 2 — Project Memory: load or create a memory store
    # ------------------------------------------------------------------
    console.print(f"\n[bold yellow]2. [Member 2] Loading Project Memory store for {project_name}...[/bold yellow]")

    # Each project gets its own memory DB stored inside .projectmind/
    # Named after the project folder so different projects don't share memories
    db_dir = project_root / ".projectmind"
    db_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c if c.isalnum() else "_" for c in project_name.lower())
    db_path = db_dir / f"{safe_name}_memory.db"

    is_fresh_db = not db_path.exists()
    repo = MemoryRepository(db_path)
    now = utc_now()

    if is_fresh_db:
        # First time scanning this project — seed some generic starter memories
        # based on what we found in the codebase
        console.print(f"  [dim]No existing memory DB found — creating fresh one for {project_name}[/dim]")

        repo.create_evidence(
            Evidence(
                id="ev-root-01",
                kind=EvidenceKind.CODE,
                file_path=str(target_path),
                description=f"{project_name} root directory",
            )
        )

        # Auto-detect what Python files exist and seed architecture memory
        py_files = list(target_path.rglob("*.py"))
        file_list = ", ".join(f.name for f in py_files[:5])
        if len(py_files) > 5:
            file_list += f" + {len(py_files) - 5} more"

        starter_memories = []

        if py_files:
            starter_memories.append(
                Memory(
                    id="mem-auto-001",
                    type=MemoryType.ARCHITECTURE,
                    content=f"{project_name} contains {len(py_files)} Python source files. "
                            f"Key files detected: {file_list}.",
                    importance=0.9,
                    confidence=0.85,
                    created_at=now,
                    updated_at=now,
                    evidence=["ev-root-01"],
                )
            )

        # Check for common patterns in the project
        has_requirements = (target_path / "requirements.txt").exists()
        has_pyproject = (target_path / "pyproject.toml").exists()
        has_tests = (target_path / "tests").exists() or any(target_path.rglob("test_*.py"))
        has_readme = (target_path / "README.md").exists() or (target_path / "README.rst").exists()

        features = []
        if has_requirements or has_pyproject:
            features.append("dependency management")
        if has_tests:
            features.append("test suite")
        if has_readme:
            features.append("documentation")

        if features:
            starter_memories.append(
                Memory(
                    id="mem-auto-002",
                    type=MemoryType.GOAL,
                    content=f"{project_name} is a Python project with: {', '.join(features)}.",
                    importance=0.8,
                    confidence=0.9,
                    created_at=now,
                    updated_at=now,
                    evidence=["ev-root-01"],
                )
            )

        starter_memories.append(
            Memory(
                id="mem-auto-003",
                type=MemoryType.CONSTRAINT,
                content=f"All code changes in {project_name} must follow the existing project structure and naming conventions.",
                importance=0.85,
                confidence=0.95,
                created_at=now,
                updated_at=now,
                evidence=["ev-root-01"],
            )
        )

        for m in starter_memories:
            repo.create_memory(m)

        console.print(
            f"  [green][OK][/green] Fresh memory store created with "
            f"[bold]{len(starter_memories)}[/bold] auto-generated memories"
        )
    else:
        console.print(f"  [dim]Found existing memory DB for {project_name}[/dim]")

    memory_service = SQLiteProjectMemory(repo)
    status = memory_service.get_status()
    console.print(
        f"  [green][OK][/green] Project Memory online "
        f"([bold]{status.total_items}[/bold] memories stored in SQLite at [dim]{db_path.name}[/dim])"
    )

    # ------------------------------------------------------------------
    # 3. Member 3 — Context Retrieval & Token Budget Controller
    # ------------------------------------------------------------------
    console.print("\n[bold yellow]3. [Member 3] Initializing Context Retrieval & Token Budget Controller...[/bold yellow]")
    retrieval_service = RetrievalService(
        code_intelligence=ci_service,
        project_memory=memory_service,
    )
    console.print("  [green][OK][/green] BM25 Search & Utility-per-token Budget Controller online")

    # ------------------------------------------------------------------
    # 4. Wire into ProjectMindCore
    # ------------------------------------------------------------------
    core = ProjectMindCore(
        code_intelligence=ci_service,
        project_memory=memory_service,
        context_retriever=retrieval_service,
    )
    console.print(
        f"\n[bold green][OK] ProjectMindCore active for {project_name}: "
        f"{core.is_fully_configured()}[/bold green]\n"
    )

    # ------------------------------------------------------------------
    # 5. Developer Task Request
    # ------------------------------------------------------------------
    console.print(
        Panel(
            f"[bold white]Developer Task Request:[/bold white]\n"
            f"[cyan]\"{developer_task}\"[/cyan]",
            border_style="blue",
        )
    )

    context = core.context_retriever.get_context(
        task=developer_task,
        token_budget=token_budget,
        include_code=True,
    )

    # ------------------------------------------------------------------
    # 6. Display Results
    # ------------------------------------------------------------------

    # Memory Table
    table_k = Table(title=f"Retrieved Project Memories (Member 2) — {project_name}")
    table_k.add_column("Category", style="cyan")
    table_k.add_column("Content / Memory", style="white", max_width=60)
    table_k.add_column("Relevance", style="green")

    if context.knowledge_items:
        for k in context.knowledge_items:
            table_k.add_row(k.category, k.content, f"{k.relevance_score:.2f}")
    else:
        table_k.add_row("[dim]—[/dim]", "[dim]No relevant memories found for this task[/dim]", "[dim]—[/dim]")

    console.print(table_k)

    # Code Chunks Table
    table_c = Table(title=f"Retrieved Code Entities from {project_name} (Member 1)")
    table_c.add_column("File Path", style="cyan", max_width=40)
    table_c.add_column("Lines", style="yellow")
    table_c.add_column("Summary", style="white", max_width=50)

    if context.code_chunks:
        for c in context.code_chunks:
            table_c.add_row(c.file_path, f"L{c.start_line}-L{c.end_line}", c.summary or "Code Snippet")
    else:
        table_c.add_row("[dim]—[/dim]", "[dim]—[/dim]", "[dim]No matching code entities found[/dim]")

    console.print(table_c)

    # Warnings
    if context.warnings:
        console.print("\n[bold red]Triggered Security & Architecture Constraints:[/bold red]")
        for w in context.warnings:
            console.print(f"  • [[bold]{w.severity.upper()}[/bold]] {w.category}: {w.message}")

    # Budget Summary
    console.print(
        Panel(
            f"[bold]Context Package Token Usage:[/bold] {context.token_count} / {token_budget} tokens\n"
            f"[dim]{context.retrieval_notes}[/dim]",
            border_style="green",
        )
    )


if __name__ == "__main__":
    args = parse_args()

    # Resolve project path
    if args.project_path:
        target = Path(args.project_path).resolve()
        if not target.exists():
            console.print(f"[bold red]ERROR:[/bold red] Path does not exist: {target}")
            sys.exit(1)
        if not target.is_dir():
            console.print(f"[bold red]ERROR:[/bold red] Path is not a folder: {target}")
            sys.exit(1)
    else:
        # Default: built-in TaskFlow API demo project
        target = project_root / "taskflow-api"
        if not target.exists():
            console.print(
                "[bold red]ERROR:[/bold red] Default demo project [cyan]taskflow-api/[/cyan] not found.\n"
                "Provide a project path: [bold]python demo.py <path-to-project>[/bold]"
            )
            sys.exit(1)

    # Resolve task
    if args.task:
        task = args.task
    else:
        console.print()
        task = Prompt.ask(
            f"[bold cyan]Enter your developer task for [green]{target.name}[/green][/bold cyan]",
            default=f"Add a new feature to {target.name}",
        )

    run_demo(target_path=target, developer_task=task, token_budget=args.budget)
