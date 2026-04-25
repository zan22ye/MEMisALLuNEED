# AGENTS.md

This repository has completed Phase 1 of the initial implementation.

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
- `docs/phase1-spec.md`: Phase 1 CLI memory substrate spec.
- `docs/superpowers/plans/2026-04-25-phase1-cli-memory-substrate.md`: Phase 1 implementation plan.
- `pyproject.toml`: Python package metadata and `mem` CLI entry point.
- `memisalluneed/`: Phase 1 Python package.
- `tests/`: Phase 1 test suite.
- `examples/memories.jsonl`: versioned example memory data.

## Implementation Roadmap

The current roadmap has six phases:

1. Phase 0: Concept and spec.
2. Phase 1: CLI memory substrate.
3. Phase 2: Session to memory formation.
4. Phase 3: Memory-centric QA loop.
5. Phase 4: External knowledge acquisition.
6. Phase 5: Memory graph and evaluation.

Phase 1 has been implemented as a CLI demo.

## Phase 1 Status

Phase 1 provides:

- `mem init`
- `mem add`
- `mem list`
- `mem show <id>`
- `mem search <query>`
- `mem export`

SQLite is the primary storage and JSONL is the export format.

Do not add an `embedding` column to SQLite. Future semantic recall should use a dedicated vector database or vector index rather than storing vectors directly in the SQLite memory table.

Implemented package layout:

```text
memisalluneed/
  __init__.py
  cli.py
  schema.py
  store.py
  search.py
  export.py
tests/
  test_cli.py
  test_export.py
  test_store.py
  test_search.py
```

Phase 1 intentionally uses keyword/token-overlap search only. It does not use embeddings or a vector database.

Validation evidence from implementation:

- `pytest -q` passed with 28 tests.
- Editable install in a temporary venv succeeded.
- `mem --help` showed all Phase 1 commands.
- Acceptance flow passed for `mem init`, `mem add`, `mem list`, `mem search`, and `mem export`.

## Next Phase Guidance

The next implementation phase should be Phase 2: Session to Memory Formation.

Do:

- add `mem chat`;
- enforce latest `k` turns or latest `k` tokens in active session context;
- roll older session context into memory;
- run lightweight per-turn memory checks;
- create memory candidates from important new information.

Do not yet implement unless Phase 2 spec changes:

- graph reasoning;
- conflict detection;
- benchmark evaluation.

## Collaboration Notes

- Prefer small, focused changes.
- Preserve the conceptual language already established in `README.md`, `README_zh.md`, and `docs/roadmap.md`.
- Before implementing a new phase, update the roadmap if the plan changes.
- Do not commit `.codex`; it is currently an untracked local file.
- Keep `.memisalluneed/`, `.worktrees/`, cache files, and generated local runtime artifacts out of git.
