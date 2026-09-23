"""Token estimation utilities."""

from __future__ import annotations

try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text))

except ImportError:

    def count_tokens(text: str) -> int:
        # Rough heuristic: ~1.3 tokens per whitespace-split word.
        words = text.split()
        return max(1, int(len(words) * 1.3))
