# ProjectMind 🧠

A local-first, model-independent project intelligence and memory layer for AI coding agents.

Instead of giving an AI the entire codebase every time, ProjectMind understands the project, remembers important things like its goal, architecture, decisions, constraints, and history. It checks whether that knowledge is still valid after code changes, and then gives the AI only the information it needs for the current task.

**This is the Platform & Agent Integration layer (Member 4) implementation.**

---

## What's Included

- **`projectmind` CLI**: Easy command-line interface to manage the project memory.
- **FastMCP Server**: Exposes 7 intelligence tools to Claude Desktop (and other agents).
- **Core Interfaces**: Defined contracts (`projectmind.core.interfaces`) that Members 1, 2, and 3 will implement.
- **Agent Adapters**: Out-of-the-box integrations for Claude Desktop and Ollama.
- **Health Doctor**: Comprehensive system checks via `projectmind doctor`.

## Installation

ProjectMind requires Python 3.11+.

```bash
git clone https://github.com/Anushree-007/projectmind.git
cd projectmind
pip install -e .
```

To install development dependencies (for testing):
```bash
pip install -e ".[dev]"
```

## Quick Start

### 1. Initialize a Project

Run this in the root of any codebase:

```bash
projectmind init
```
This creates a `.projectmind/` directory and a `projectmind.toml` configuration file.

### 2. Index the Codebase

Build the initial code index and project memory (requires Members 1 & 2):

```bash
projectmind index
```

### 3. Connect Your Agent

To connect Claude Desktop automatically:
```bash
projectmind connect claude
```

To see integration instructions for a local Ollama agent:
```bash
projectmind connect ollama
```

### 4. Start the MCP Server

Start the FastMCP server so your AI agent can talk to ProjectMind:

```bash
projectmind serve
```

## CLI Reference

ProjectMind offers a rich CLI for exploring project memory without an AI:

| Command | Description |
|---|---|
| `projectmind init` | Initialize ProjectMind in the current directory |
| `projectmind index` | Parse codebase and build memory |
| `projectmind doctor` | Run health checks |
| `projectmind status` | View index and memory freshness |
| `projectmind query "<text>"` | Search project decisions, goals, constraints |
| `projectmind context "<task>"` | Generate an optimal context payload for a task |
| `projectmind audit` | Audit memory for stale or contradicted items |
| `projectmind serve` | Start the MCP server |
| `projectmind connect` | Agent configuration generators |

## MCP Tools Exposed

ProjectMind exposes these tools via MCP:

- `get_project_summary()`: High-level orientation for an AI agent.
- `search_project_knowledge()`: Natural language search over project decisions and history.
- `get_relevant_code()`: Semantically retrieve code chunks for a query.
- `get_project_context()`: Assemble task-specific context (code + knowledge + warnings).
- `get_project_warnings()`: Identify constraint violations for a proposed task.
- `audit_project()`: Find stale knowledge.
- `get_project_status()`: System health.

## Development

Run the test suite using pytest. The tests use deterministic stubs for Members 1, 2, and 3, so they run fast without requiring actual code analysis.

```bash
pytest tests/ -v
```

Run linting and type checking:
```bash
ruff check .
mypy projectmind/platform projectmind/core
```
