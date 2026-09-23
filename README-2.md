# ProjectMind — Retrieval & Context Optimization (Member 3)

Task-aware retrieval and context assembly module for **ProjectMind**, a
local-first, model-independent project intelligence and memory layer for
AI coding agents.

This module answers: *given a user's question, exactly what information
should we hand the AI agent, within a token budget?*

## Status: independent, mock-data-driven build

This module has **no runtime dependency on Member 1 (Repository
Intelligence) or Member 2 (Knowledge & Memory)**. It is built and tested
against `src/mock_data.py`, which produces `MemoryRecord` and `CodeEntity`
objects in the exact shape defined by the team's shared contracts
(`src/contracts.py` — mirrors `docs/contracts/memory.schema.json` and
`code_entity.schema.json`). When the real modules are ready, only the data
source changes; retrieval, budgeting and assembly logic does not.

## Pipeline

```
Query
  -> BM25 keyword retrieval        (src/bm25_retrieval.py)
  -> Utility scoring                (src/budget_controller.py)
  -> Budget-constrained selection   (src/budget_controller.py)
  -> Context package assembly       (src/context_assembly.py)
```

Per the project's revised design decisions, **BM25/structured retrieval
comes first**. Semantic search / embeddings / Qdrant are only added in a
later phase, and only if they measurably improve the benchmark in
`src/benchmark.py` — complexity has to earn its place.

## Structure

```
projectmind-retrieval/
├── src/
│   ├── contracts.py          # shared data contracts (Memory, CodeEntity, ContextPackage)
│   ├── mock_data.py          # mock memory/code data — unblocks independent dev
│   ├── bm25_retrieval.py     # Phase 1: BM25 keyword retrieval
│   ├── token_utils.py        # token counting (tiktoken, with fallback)
│   ├── budget_controller.py  # Phase 8: utility scoring + budget selection
│   ├── context_assembly.py   # Phase 6/7: context package assembly + compression
│   └── benchmark.py          # Phase 9: with vs. without ProjectMind benchmark
├── tests/                    # unit tests for each component
├── examples/
│   └── demo.py                # end-to-end runnable demo
└── requirements.txt
```

## Setup

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

## Run the demo

```bash
python -m examples.demo
```

Example output:

```
--- Benchmark: with vs without ProjectMind ---
  without ProjectMind: 176 tokens (everything)
  with ProjectMind:    57 tokens
  token reduction:     67.6%
  relevant items retained: 3/5
```

## Run tests

```bash
python -m pytest tests/ -v
```

## Scoring model

```
utility = relevance × importance × confidence × freshness
```

The budget controller selects the highest-utility combination of items
that fits within the configured token budget (greedy by utility-per-token
density), rather than optimizing for token count alone.

## Roadmap (this module)

- [x] Phase 1 — BM25 keyword retrieval
- [x] Phase 6/7 — Context assembly + compression
- [x] Phase 8 — Budget controller
- [x] Phase 9 — With/without benchmark
- [ ] Phase 2 — Semantic (embedding) retrieval — pending benchmark justification
- [ ] Phase 4 — Hybrid retrieval (BM25 + semantic via RRF)
- [ ] Phase 5 — Cross-encoder reranking
- [ ] Swap `mock_data.py` for Member 2's real memory store and Member 1's
      real repository analyzer once their contracts are finalized

## Explicitly out of scope for this module

- Repository parsing / code analysis (Member 1)
- Memory lifecycle, contradiction/staleness detection (Member 2)
- MCP server, CLI, Claude Desktop packaging (Member 4)
