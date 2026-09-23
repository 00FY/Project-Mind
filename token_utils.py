"""
Token estimation.

Uses `tiktoken` if it's installed (accurate, matches OpenAI/Claude-style
BPE tokenization closely enough for budgeting purposes); falls back to a
whitespace-based heuristic if it isn't, so this module never hard-fails
just because a dependency is missing.
"""

from __future__ import annotations

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text))

except ImportError:  # pragma: no cover - exercised when tiktoken isn't installed

    def count_tokens(text: str) -> int:
        # Rough heuristic: ~1.3 tokens per whitespace-split word.
        words = text.split()
        return max(1, int(len(words) * 1.3))
