# Phase 1 Spec: CLI Memory Substrate

Phase 1 builds the first runnable MEMisALLuNEED prototype.

The milestone is intentionally small: a command-line memory substrate that can create, store, recall, inspect, and export memory items without relying on an LLM.

## Goal

Build a minimal local CLI demo that proves the storage-recall-export loop works.

Phase 1 should answer one question:

> Can a unified memory item be written, persisted, recalled, inspected, and exported?

## Non-Goals

Phase 1 should not implement:

- LLM-based memory formation;
- session rolling write;
- automatic query-answer memory creation;
- external knowledge acquisition;
- memory graph reasoning;
- conflict detection;
- outdated-memory detection;
- benchmark evaluation.

These belong to later phases.

## CLI Entry

The CLI command name is:

```bash
mem
```

## CLI Contract

### `mem init`

Initialize a local memory database.

Default behavior:

- create `.memisalluneed/` if it does not exist;
- create `.memisalluneed/memory.db`;
- create required SQLite tables;
- be safe to run multiple times.

Options:

- `--db <path>`: use a custom database path.

Example:

```bash
mem init
mem init --db /tmp/memory.db
```

### `mem add "content"`

Add one memory item.

Default behavior:

- `type=knowledge`;
- `state=success`;
- `confidence=1.0`;
- `metadata={}`.

Options:

- `--type <type>`: memory type.
- `--state <state>`: memory state.
- `--confidence <float>`: confidence score.
- `--metadata <json>`: JSON metadata object.
- `--db <path>`: use a custom database path.

Example:

```bash
mem add "Everything before the current moment can be treated as memory."
mem add "External knowledge is acquired only when memory is insufficient." --type knowledge --confidence 0.9
```

### `mem list`

List stored memory items.

Default behavior:

- sort by `created_at` descending;
- show a compact table;
- include `id`, `type`, `state`, `confidence`, content preview, and `created_at`.

Options:

- `--limit <n>`: maximum number of rows, default `20`.
- `--db <path>`: use a custom database path.

Example:

```bash
mem list
mem list --limit 50
```

### `mem show <id>`

Show one complete memory item.

Default behavior:

- print the full item in a readable structured format;
- include metadata and timestamps.

Options:

- `--json`: print raw JSON.
- `--db <path>`: use a custom database path.

Example:

```bash
mem show 01HX...
mem show 01HX... --json
```

### `mem search "query"`

Recall relevant memory items.

Default behavior:

- return top `5` results;
- use lightweight text similarity;
- display similarity score;
- update `usage_count`;
- update `last_recalled_at`.

Options:

- `--top-k <n>`: number of results, default `5`.
- `--db <path>`: use a custom database path.

Example:

```bash
mem search "when should external knowledge be used"
mem search "memory substrate" --top-k 10
```

### `mem export`

Export memory items as JSONL.

Default behavior:

- write JSONL to stdout;
- one memory item per line.

Options:

- `--output <path>`: write JSONL to a file.
- `--db <path>`: use a custom database path.

Example:

```bash
mem export
mem export --output examples/memories.jsonl
```

## Data Model

Phase 1 uses a unified `MemoryItem` model.

Required fields:

- `id`: stable memory id.
- `type`: memory type.
- `content`: memory content.
- `state`: memory state.
- `confidence`: confidence score.
- `metadata`: JSON metadata object.
- `created_at`: creation timestamp.
- `updated_at`: last update timestamp.
- `usage_count`: number of times recalled.
- `last_recalled_at`: last recall timestamp, nullable.

## Memory Types

Phase 1 should support the type field without enforcing complex behavior.

Allowed initial values:

- `knowledge`;
- `experience`;
- `recall`;
- `source`.

Default:

- `knowledge`.

## Memory States

Allowed initial values:

- `success`;
- `failed`;
- `uncertain`;
- `contradicted`;
- `outdated`.

Default:

- `success`.

## SQLite Schema

Phase 1 should create a `memories` table.

Suggested schema:

```sql
CREATE TABLE IF NOT EXISTS memories (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,
  content TEXT NOT NULL,
  state TEXT NOT NULL,
  confidence REAL NOT NULL,
  metadata TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  usage_count INTEGER NOT NULL DEFAULT 0,
  last_recalled_at TEXT
);
```

Recommended indexes:

```sql
CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type);
CREATE INDEX IF NOT EXISTS idx_memories_state ON memories(state);
CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at);
```

Phase 1 does not need to implement graph edges, but the architecture should not block a future `memory_edges` table.

Future graph table:

```sql
CREATE TABLE IF NOT EXISTS memory_edges (
  id TEXT PRIMARY KEY,
  source_memory_id TEXT NOT NULL,
  target_memory_id TEXT NOT NULL,
  relation_type TEXT NOT NULL,
  metadata TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

## Search Algorithm

Phase 1 should use lightweight local text similarity.

Phase 1 should not implement embeddings and should not add an `embedding` column to SQLite.

Future semantic recall should use a dedicated vector database or vector index. SQLite remains the canonical structured memory store, while the vector database becomes a separate recall index when introduced in a later phase.

Recommended baseline:

1. Normalize query and memory content to lowercase.
2. Tokenize on non-word boundaries.
3. Remove empty tokens.
4. Score each memory with token overlap.
5. Return highest scoring memories.

Suggested score:

```text
score = overlap(query_tokens, memory_tokens) / len(query_tokens)
```

Tie-breakers:

1. Higher score.
2. Higher confidence.
3. More recent `created_at`.

When a memory is returned by `mem search`, update:

- `usage_count += 1`;
- `last_recalled_at = now`.

## File and Directory Strategy

Runtime data:

- default directory: `.memisalluneed/`;
- default database: `.memisalluneed/memory.db`.

Repository policy:

- `.memisalluneed/` should be added to `.gitignore`;
- local runtime databases should not be committed.

Example data:

- provide versioned example data at `examples/memories.jsonl`;
- example data should be human-readable;
- example data can be used in docs and tests.

## Suggested Package Layout

```text
MEMisALLuNEED/
  pyproject.toml
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
  examples/
    memories.jsonl
```

## Module Responsibilities

### `schema.py`

Defines:

- `MemoryItem`;
- allowed memory types;
- allowed memory states;
- serialization helpers.

### `store.py`

Handles:

- database initialization;
- inserting memory items;
- listing memory items;
- fetching by id;
- updating recall metadata.

### `search.py`

Handles:

- text normalization;
- tokenization;
- overlap scoring;
- ranked search.

### `export.py`

Handles:

- JSONL serialization;
- stdout export;
- file export.

### `cli.py`

Defines the `mem` CLI and maps commands to store/search/export behavior.

## Testing Plan

Use temporary database files in tests.

Minimum tests:

- initialize database;
- add memory item;
- list memory items;
- fetch memory item by id;
- search returns relevant item;
- search updates `usage_count`;
- search updates `last_recalled_at`;
- export writes valid JSONL.

Do not depend on `.memisalluneed/` in tests.

## Acceptance Criteria

The following flow should work:

```bash
mem init
mem add "Everything before the current moment can be treated as memory."
mem add "External knowledge is acquired only when memory is insufficient."
mem list
mem search "when should external knowledge be used"
mem show <id>
mem export
mem export --output examples/memories.jsonl
```

Phase 1 is complete when:

- the CLI entry `mem` works;
- SQLite storage works;
- memory items can be added and listed;
- memory items can be searched with text similarity;
- recalled items update usage metadata;
- memory items can be exported as JSONL;
- `.memisalluneed/` is ignored by git;
- example JSONL data exists;
- minimal store and search tests pass.
