"""
Phase 1 — Basic Keyword Search (BM25).

Per the revised plan: build this first, and only add semantic/Qdrant
retrieval later if it demonstrably improves the benchmark (see benchmark.py).
"""

from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from .contracts import CodeEntity, MemoryRecord, RetrievalResult

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> list[str]:
    """Simple, dependency-free tokenizer good enough for BM25 over code/prose."""
    return [t.lower() for t in _TOKEN_RE.findall(text)]


class BM25Retriever:
    """
    Wraps rank_bm25 over a mixed corpus of MemoryRecord and CodeEntity
    objects, indexing memory content and code names/snippets together
    but tagging each result with its item type for downstream logic.
    """

    def __init__(self, memories: list[MemoryRecord], code_entities: list[CodeEntity]):
        self.memories = memories
        self.code_entities = code_entities
        self._items: list[tuple[str, object]] = (
            [("memory", m) for m in memories] + [("code", c) for c in code_entities]
        )
        corpus = [self._text_for(item_type, item) for item_type, item in self._items]
        self._tokenized_corpus = [_tokenize(doc) for doc in corpus]
        self._bm25 = BM25Okapi(self._tokenized_corpus)

    @staticmethod
    def _text_for(item_type: str, item: object) -> str:
        if item_type == "memory":
            m: MemoryRecord = item  # type: ignore[assignment]
            return f"{m.type.value} {m.content} {m.source}"
        c: CodeEntity = item  # type: ignore[assignment]
        return f"{c.name} {c.file} {c.kind} {c.snippet or ''}"

    def search(self, query: str, top_k: int = 10) -> list[RetrievalResult]:
        tokens = _tokenize(query)
        scores = self._bm25.get_scores(tokens)

        ranked = sorted(
            zip(self._items, scores), key=lambda pair: pair[1], reverse=True
        )

        results: list[RetrievalResult] = []
        for (item_type, item), score in ranked[:top_k]:
            if score <= 0:
                continue
            item_id = item.id
            results.append(
                RetrievalResult(
                    item_id=item_id,
                    item_type=item_type,
                    score=float(score),
                    bm25_score=float(score),
                    matched_item=item,
                )
            )
        return results
