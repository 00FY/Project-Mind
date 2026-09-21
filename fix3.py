def fix_ollama():
    path = "projectmind/platform/adapters/ollama.py"
    with open(path, encoding="utf8") as f:
        c = f.read()
    # Safely replace the template string
    if "{" in c and "{{" not in c:
        # Use regex to replace { and } with {{ and }} but keep {host} and {model} intact
        c = c.replace('{\n  "mcpServers"', '{{\n  "mcpServers"')
        c = c.replace('"ProjectMind": {', '"ProjectMind": {{')
        c = c.replace('"args": []\n    }', '"args": []\n    }}')
        c = c.replace("  }\n}", "  }}\n}}")
        c = c.replace('{\n    "name"', '{{\n    "name"')
        c = c.replace('"args": []\n}', '"args": []\n}}')
        with open(path, "w", encoding="utf8") as f:
            f.write(c)


def fix_stubs():
    path = "tests/stubs.py"
    with open(path, encoding="utf8") as f:
        c = f.read()

    old = """        q = query.lower()
        words = [w for w in q.split() if len(w) > 2]"""
    new = """        import re
        q = re.sub(r'[^\\w\\s]', '', query.lower())
        words = [w for w in q.split() if len(w) > 2]"""
    if old in c:
        c = c.replace(old, new)
        with open(path, "w", encoding="utf8") as f:
            f.write(c)


def debug_doctor():
    # Write a script that checks what's in stdout for doctor --json-output
    script = """from click.testing import CliRunner
from projectmind.platform.cli.main import cli
import sys
r = CliRunner().invoke(cli, ['doctor', '--json-output'])
with open('debug_doctor.txt', 'w', encoding='utf8') as f:
    f.write(repr(r.output))
"""
    with open("debug_doctor.py", "w", encoding="utf8") as f:
        f.write(script)


fix_ollama()
fix_stubs()
debug_doctor()
print("fixes applied")
