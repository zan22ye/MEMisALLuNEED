# AGENTS.md

This repository is currently in the concept and early implementation planning stage.

## Project Summary

MEMisALLuNEED is a Memory-Centric Agent project.

The core thesis is:

> Everything before the current moment can be treated as memory.

The system should rely on a growing memory substrate rather than an ever-growing context window.

## Current Decisions

- The framing is **Memory-Centric Agent**.
- The system uses a unified `MemoryItem` model.
- Memory items are connected through an explicit memory graph.
- Memory types include knowledge, experience, recall, and source reference.
- External knowledge is not added by default.
- External knowledge is acquired only when existing memory is insufficient.
- External source full text is not stored by default; source references are stored.
- Memory is automatically written after cleaning, compression, and structuring.
- Failed, uncertain, outdated, and contradicted memories are still written with state metadata.
- Sessions keep only the latest `k` turns or latest `k` tokens.
- Older session content is rolled into memory and later reused through recall.
- Rolling memory write plus per-turn lightweight checks are preferred.

## Current Files

- `README.md`: English project overview.
- `README_zh.md`: Chinese project overview.
- `docs/roadmap.md`: staged implementation roadmap.

## Implementation Roadmap

The current roadmap has six phases:

1. Phase 0: Concept and spec.
2. Phase 1: CLI memory substrate.
3. Phase 2: Session to memory formation.
4. Phase 3: Memory-centric QA loop.
5. Phase 4: External knowledge acquisition.
6. Phase 5: Memory graph and evaluation.

Phase 1 should be implemented first as a CLI demo.

## Phase 1 Direction

The first runnable prototype should provide:

- `mem init`
- `mem add`
- `mem list`
- `mem show <id>`
- `mem search <query>`
- `mem export`

Use SQLite as the primary storage and JSONL as the export format.

Suggested package layout:

```text
memisalluneed/
  __init__.py
  cli.py
  schema.py
  store.py
  search.py
  export.py
tests/
  test_store.py
  test_search.py
```

## Scope Guidance

For Phase 1, keep implementation minimal.

Do:

- implement local memory storage;
- implement basic memory item schema;
- implement simple text search;
- implement JSONL export;
- add minimal tests for store and search.

Do not yet implement:

- LLM-based memory formation;
- session rolling write;
- external knowledge acquisition;
- graph reasoning;
- conflict detection;
- benchmark evaluation.

## Collaboration Notes

- Prefer small, focused changes.
- Preserve the conceptual language already established in `README.md`, `README_zh.md`, and `docs/roadmap.md`.
- Before implementing a new phase, update the roadmap if the plan changes.
- Do not commit `.codex`; it is currently an untracked local file.
