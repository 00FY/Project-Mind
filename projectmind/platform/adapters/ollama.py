"""
Ollama adapter for ProjectMind.

Provides an integration path for local Ollama agents using the
OpenAI-compatible API. This adapter shows how to call ProjectMind
context tools from a Python agent script that uses Ollama.

This is NOT a full agent implementation — it is a reference integration
that demonstrates how to wire ProjectMind into any OpenAI-compatible
local LLM.
"""

from __future__ import annotations

from typing import Any

from projectmind.platform.adapters.base import AgentAdapter, register_adapter
from projectmind.platform.logging.setup import get_logger

logger = get_logger("adapters.ollama")

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.syntax import Syntax
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False
    console = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Integration guide printer
# ---------------------------------------------------------------------------

_INTEGRATION_GUIDE_TEMPLATE = '''\
"""
ProjectMind + Ollama Integration Example
=========================================
This script shows how to call ProjectMind context tools from a local
Ollama agent using the OpenAI-compatible API.

Requirements:
    pip install openai projectmind
    ollama pull {model}
    projectmind serve --transport sse --port 3333 &
"""

import json
from openai import OpenAI

# ---------------------------------------------------------------------------
# Connect to Ollama (OpenAI-compatible API)
# ---------------------------------------------------------------------------
ollama_client = OpenAI(
    base_url="{host}/v1",
    api_key="ollama",  # required but unused by Ollama
)

# ---------------------------------------------------------------------------
# ProjectMind tools definition (for Ollama function-calling)
# ---------------------------------------------------------------------------
PROJECTMIND_TOOLS = [
    {{
        "type": "function",
        "function": {{
            "name": "get_project_context",
            "description": (
                "Get the minimum-sufficient context for an AI agent to work on a task. "
                "Returns relevant project knowledge, code, and warnings within a token budget."
            ),
            "parameters": {{
                "type": "object",
                "properties": {{
                    "task": {{"type": "string", "description": "The task description"}},
                    "token_budget": {{"type": "integer", "description": "Max tokens (default 8000)"}},
                }},
                "required": ["task"],
            }},
        }},
    }},
    {{
        "type": "function",
        "function": {{
            "name": "search_project_knowledge",
            "description": "Search project knowledge base with a natural language query.",
            "parameters": {{
                "type": "object",
                "properties": {{
                    "query": {{"type": "string"}},
                    "limit": {{"type": "integer", "default": 10}},
                }},
                "required": ["query"],
            }},
        }},
    }},
]

# ---------------------------------------------------------------------------
# ProjectMind MCP client (SSE transport)
# ---------------------------------------------------------------------------
import httpx

def call_projectmind_tool(tool_name: str, **kwargs) -> dict:
    """Call a ProjectMind MCP tool via HTTP (SSE transport)."""
    response = httpx.post(
        "http://localhost:3333/call",
        json={{"tool": tool_name, "arguments": kwargs}},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------
def run_agent(task: str) -> str:
    """Run an Ollama agent with ProjectMind context for a given task."""
    print(f"\\n🤖 Agent starting task: {{task}}\\n")

    # Step 1: Get ProjectMind context
    print("📚 Fetching ProjectMind context...")
    context = call_projectmind_tool("get_project_context", task=task)
    warnings = context.get("warnings", [])

    # Step 2: Build system prompt with project context
    system_prompt = build_system_prompt(context)

    messages = [
        {{"role": "system", "content": system_prompt}},
        {{"role": "user", "content": task}},
    ]

    # Step 3: Call Ollama with project-aware system prompt
    response = ollama_client.chat.completions.create(
        model="{model}",
        messages=messages,
        tools=PROJECTMIND_TOOLS,
    )

    # Handle tool calls if the model requests more info
    message = response.choices[0].message
    if message.tool_calls:
        for tool_call in message.tool_calls:
            args = json.loads(tool_call.function.arguments)
            result = call_projectmind_tool(tool_call.function.name, **args)
            messages.append(message)
            messages.append({{
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            }})

        # Get final response
        final = ollama_client.chat.completions.create(
            model="{model}",
            messages=messages,
        )
        return final.choices[0].message.content

    return message.content


def build_system_prompt(context: dict) -> str:
    """Build a project-aware system prompt from ProjectMind context."""
    lines = [
        "You are a project-aware AI coding assistant.",
        "",
        "=== PROJECT CONTEXT ===",
    ]

    if summary := context.get("project_summary"):
        lines.append(f"Project: {{summary['name']}} — {{summary['description']}}")

    if warnings := context.get("warnings", []):
        lines.append("\\n⚠ ACTIVE WARNINGS:")
        for w in warnings:
            lines.append(f"  [{{w['severity'].upper()}}] {{w['message']}}")

    if items := context.get("knowledge_items", []):
        lines.append("\\n📖 RELEVANT KNOWLEDGE:")
        for item in items[:5]:  # top 5
            lines.append(f"  • {{item['title']}}: {{item['content'][:200]}}")

    lines.append("\\n=== END CONTEXT ===")
    lines.append("Always respect project constraints and decisions shown above.")
    return "\\n".join(lines)


if __name__ == "__main__":
    import sys
    task = " ".join(sys.argv[1:]) or "Explain the project architecture"
    result = run_agent(task)
    print("\\n" + "="*60)
    print(result)
'''


def print_ollama_integration_guide(host: str = "http://localhost:11434", model: str = "llama3") -> None:
    """Print the Ollama integration guide to stdout."""
    code = _INTEGRATION_GUIDE_TEMPLATE.format(host=host, model=model)
    if _RICH:
        console.print(
            Panel(
                f"[bold]Ollama Integration Guide[/bold]\n\n"
                f"Host: [cyan]{host}[/cyan]  Model: [cyan]{model}[/cyan]\n\n"
                f"To use ProjectMind with Ollama:\n"
                f"  1. Start ProjectMind MCP server:\n"
                f"       [bold]projectmind serve --transport sse --port 3333[/bold]\n"
                f"  2. Use the code below in your Ollama agent script.",
                title="Ollama Adapter",
                border_style="blue",
            )
        )
        console.print(Syntax(code, "python", theme="monokai", line_numbers=True))
    else:
        print("# Ollama Integration Guide")
        print(f"# Host: {host}, Model: {model}")
        print(code)


# ---------------------------------------------------------------------------
# Adapter implementation
# ---------------------------------------------------------------------------


@register_adapter
class OllamaAdapter(AgentAdapter):
    """
    Adapter for local Ollama agents (OpenAI-compatible API).

    Formats ProjectMind context as a system-prompt-ready string
    suitable for injection into any OpenAI-compatible API call.
    """

    name = "Ollama"
    identifier = "ollama"

    def format_context(self, context: dict[str, Any]) -> str:
        """Format context as a system prompt injection."""
        lines = ["=== PROJECT CONTEXT (from ProjectMind) ==="]

        if summary := context.get("project_summary"):
            lines.append(f"Project: {summary.get('name')} — {summary.get('description', '')}")

        if warnings := context.get("warnings", []):
            lines.append("\n⚠ ACTIVE WARNINGS:")
            for w in warnings:
                lines.append(f"  [{w['severity'].upper()}] {w['message']}")

        if items := context.get("knowledge_items", []):
            lines.append("\nRELEVANT KNOWLEDGE:")
            for item in items:
                lines.append(f"  • {item['title']}: {item['content']}")

        if chunks := context.get("code_chunks", []):
            lines.append("\nRELEVANT CODE:")
            for chunk in chunks:
                lines.append(
                    f"  File: {chunk['file_path']} L{chunk['start_line']}-{chunk['end_line']}\n"
                    f"  ```\n  {chunk['content'][:500]}\n  ```"
                )

        lines.append("=== END CONTEXT ===")
        return "\n".join(lines)

    def format_knowledge(self, items: list[dict[str, Any]]) -> str:
        """Format knowledge items as plain text."""
        if not items:
            return "No relevant knowledge found."
        return "\n".join(
            f"- {item['title']} ({item['category']}, {item['status']}): {item['content']}"
            for item in items
        )

    def format_warning(self, warnings: list[dict[str, Any]]) -> str:
        """Format warnings as plain text."""
        if not warnings:
            return "No warnings for this task."
        return "\n".join(
            f"[{w['severity'].upper()}] {w['message']}"
            for w in warnings
        )
