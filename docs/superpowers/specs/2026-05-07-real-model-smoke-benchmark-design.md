# Real-Model Smoke Benchmark Design

## Goal

Build a pytest-runnable real-model integration test suite that verifies the
core MEMisALLuNEED memory paths work end to end.

This benchmark is a smoke benchmark, not a model intelligence benchmark. It
uses simple, low-ambiguity cases and tolerant assertions to check whether the
system's memory recall, chat formation, timestamp-aware resolution, trace, and
export paths function correctly with real configured models.

The benchmark should verify that:

- existing memories can be recalled and used by `mem chat`;
- `mem chat` can write session content into memory through the real formation
  model;
- timestamp-aware resolution prefers newer relevant memories while preserving
  older memories;
- memory trace output and JSONL export preserve required structure and
  metadata.

## Scope

The first version includes four required subsets:

```text
recall_qa
session_formation
timestamp_resolution
trace_export
```

Each subset contains two cases. The full first version contains eight required
cases.

Host integration is out of the required first version. It can be added later as
an optional subset because it validates the Phase 4 plugin boundary rather than
the core `mem chat` path.

## Non-Goals

This benchmark does not test:

- web search;
- external crawling;
- benchmark leaderboard scoring;
- exact-match natural language answers;
- complex multi-hop reasoning;
- graph reasoning;
- conflict detection;
- embedding or vector recall;
- full source text storage;
- host integration in the required first version.

## Dataset Layout

Datasets live under:

```text
datasets/smoke_real_model/
  recall_qa.jsonl
  session_formation.jsonl
  timestamp_resolution.jsonl
  trace_export.jsonl
```

A future optional host integration subset may live at:

```text
datasets/smoke_real_model/host_integration_optional.jsonl
```

Each JSONL file contains one case per line.

## Case Schema

All subsets use a shared JSON object shape:

```json
{
  "id": "recall_qa_001",
  "category": "recall_qa",
  "description": "Answer from an existing user preference memory.",
  "setup_memories": [
    {
      "type": "knowledge",
      "content": "Alice prefers concise technical answers.",
      "state": "success",
      "confidence": 1.0,
      "created_at": "2026-05-01T10:00:00Z",
      "metadata": {
        "fixture": true
      }
    }
  ],
  "chat_messages": [
    "How should responses to Alice be styled?"
  ],
  "expected": {
    "answer_should_contain_any": ["concise", "technical"],
    "trace_should_include_memory": true,
    "min_total_memories": 1,
    "memory_types_should_include": [],
    "metadata_should_include": {}
  }
}
```

### Core Fields

- `id`: stable case id.
- `category`: subset name.
- `description`: human-readable case description.
- `setup_memories`: memory fixtures inserted before the case runs.
- `chat_messages`: user messages sent to `mem chat` in order.
- `expected`: tolerant assertions for the case.

### Expected Fields

The first runner supports these expected fields:

```json
{
  "answer_should_contain_any": ["..."],
  "answer_should_contain_all": ["..."],
  "trace_should_include_memory": true,
  "min_total_memories": 1,
  "min_new_memories": 0,
  "memory_types_should_include": ["experience"],
  "metadata_should_include": {
    "formation_kind": "chat_qa"
  },
  "export_should_parse": true,
  "old_memory_should_remain": true
}
```

The runner should treat missing expected fields as disabled assertions.

## Execution Mode

The real-model benchmark is skipped by default. It only runs when explicitly
enabled:

```bash
RUN_REAL_MODEL_TESTS=1 pytest tests/real_model -q
```

The pytest file should be:

```text
tests/real_model/test_smoke_real_model.py
```

The tests should be marked:

```python
@pytest.mark.real_model
```

If `RUN_REAL_MODEL_TESTS` is not set to `1`, all real-model tests should be
skipped.

## Configuration

The runner resolves config in this order:

1. `MEMISALLUNEED_TEST_CONFIG`
2. `.memisalluneed/config.toml`

If no config file exists, the tests should skip.

The runner should inspect the configured chat and formation providers and check
their `api_key_env` values. If a required API key environment variable is
missing, the tests should skip. If chat and formation use different providers,
both required API key environment variables must exist.

Real model API failures, timeouts, or malformed responses are test failures,
not skips.

## Runner Behavior

Each case runs in an isolated temporary directory:

```text
tmp_path/<case_id>/
  memory.db
  artifacts/
```

For each case, the runner should:

1. create an independent SQLite database;
2. insert `setup_memories`;
3. record the number and identity of setup memories;
4. invoke `mem chat` with the temporary database, selected config, and
   `--show-memory-trace`;
5. send `chat_messages` in order;
6. exit chat normally through the supported CLI exit path so flush formation
   runs;
7. capture stdout and stderr;
8. inspect the final database state;
9. run `mem export` against the temporary database;
10. run the expected assertions;
11. write artifacts.

The runner should use a reasonable per-case timeout, such as 120 seconds.

The real-model cases should not be run in parallel. This avoids rate-limit
noise and keeps artifact output easy to inspect.

## Assertion Rules

Assertions must be tolerant because real model output is not deterministic.

### Answer Assertions

- `answer_should_contain_any`: at least one keyword must appear in stdout.
- `answer_should_contain_all`: every keyword must appear in stdout.
- English keyword matching is case-insensitive.
- Chinese keyword matching uses direct substring matching.
- The runner must not require exact natural language answer matches.

### Memory Assertions

- `min_total_memories`: final memory count must be at least this value.
- `min_new_memories`: final memory count minus setup memory count must be at
  least this value.
- `memory_types_should_include`: the final database must contain at least one
  memory of each listed type.
- `metadata_should_include`: at least one memory metadata object must contain
  the specified key-value pairs.
- `old_memory_should_remain`: setup memories must still exist by id or content
  after the case completes.

### Trace Assertions

When `trace_should_include_memory` is true:

- stdout must include `Used memories:`;
- the trace must not only report `none`.

The assertion does not require exact memory id matching. Timestamp resolution
cases may show both newer and older memories in the trace. The important check
is that the answer uses the newer memory.

### Export Assertions

When `export_should_parse` is true:

- `mem export --db <tmp db>` must exit with code 0;
- each non-empty line must parse as a JSON object;
- each exported object must include:
  - `id`;
  - `type`;
  - `content`;
  - `state`;
  - `confidence`;
  - `metadata`;
  - `created_at`;
  - `updated_at`.

## Artifacts

Each case should write:

```text
artifacts/
  case.json
  stdout.txt
  stderr.txt
  export.jsonl
  memories.json
```

The runner may also write:

```text
artifacts/
  command.txt
  config_path.txt
```

Artifacts live in pytest temporary directories and are not committed.

## Required Cases

### `recall_qa.jsonl`

#### `recall_qa_001`

Purpose: answer from an existing user preference memory.

```json
{
  "id": "recall_qa_001",
  "category": "recall_qa",
  "description": "Answer from an existing user preference memory.",
  "setup_memories": [
    {
      "type": "knowledge",
      "content": "Alice prefers concise technical answers.",
      "state": "success",
      "confidence": 1.0,
      "created_at": "2026-05-01T10:00:00Z",
      "metadata": {"fixture": true}
    }
  ],
  "chat_messages": [
    "How should responses to Alice be styled?"
  ],
  "expected": {
    "answer_should_contain_any": ["concise", "technical"],
    "trace_should_include_memory": true,
    "min_total_memories": 1
  }
}
```

#### `recall_qa_002`

Purpose: answer from an existing project storage memory.

```json
{
  "id": "recall_qa_002",
  "category": "recall_qa",
  "description": "Answer from an existing project storage memory.",
  "setup_memories": [
    {
      "type": "knowledge",
      "content": "MEMisALLuNEED uses SQLite as primary storage and JSONL as export format.",
      "state": "success",
      "confidence": 1.0,
      "created_at": "2026-05-01T11:00:00Z",
      "metadata": {"fixture": true}
    }
  ],
  "chat_messages": [
    "What storage and export formats does MEMisALLuNEED use?"
  ],
  "expected": {
    "answer_should_contain_all": ["SQLite", "JSONL"],
    "trace_should_include_memory": true,
    "min_total_memories": 1
  }
}
```

### `session_formation.jsonl`

#### `session_formation_001`

Purpose: a simple user preference should be formed into memory after chat exits.

```json
{
  "id": "session_formation_001",
  "category": "session_formation",
  "description": "A simple user preference should be formed into memory after chat exits.",
  "setup_memories": [],
  "chat_messages": [
    "Remember that my default language is Chinese.",
    "What is my default language?"
  ],
  "expected": {
    "answer_should_contain_any": ["Chinese", "中文"],
    "min_new_memories": 1,
    "memory_types_should_include": ["experience"],
    "metadata_should_include": {
      "formation_kind": "chat_qa"
    }
  }
}
```

#### `session_formation_002`

Purpose: a simple project fact should be captured during chat formation.

```json
{
  "id": "session_formation_002",
  "category": "session_formation",
  "description": "A simple project fact should be captured during chat formation.",
  "setup_memories": [],
  "chat_messages": [
    "Remember that my project codename is Lantern.",
    "What is my project codename?"
  ],
  "expected": {
    "answer_should_contain_any": ["Lantern"],
    "min_new_memories": 1,
    "memory_types_should_include": ["experience"],
    "metadata_should_include": {
      "formation_kind": "chat_qa"
    }
  }
}
```

### `timestamp_resolution.jsonl`

#### `timestamp_resolution_001`

Purpose: prefer the newer editor preference memory.

```json
{
  "id": "timestamp_resolution_001",
  "category": "timestamp_resolution",
  "description": "Prefer the newer editor preference memory.",
  "setup_memories": [
    {
      "type": "knowledge",
      "content": "Alice's preferred editor is Vim.",
      "state": "success",
      "confidence": 1.0,
      "created_at": "2026-05-01T10:00:00Z",
      "metadata": {"fixture": true}
    },
    {
      "type": "knowledge",
      "content": "Alice's preferred editor is VS Code.",
      "state": "success",
      "confidence": 1.0,
      "created_at": "2026-05-03T10:00:00Z",
      "metadata": {"fixture": true}
    }
  ],
  "chat_messages": [
    "What is Alice's preferred editor now?"
  ],
  "expected": {
    "answer_should_contain_any": ["VS Code", "Visual Studio Code"],
    "trace_should_include_memory": true,
    "min_total_memories": 2,
    "old_memory_should_remain": true
  }
}
```

#### `timestamp_resolution_002`

Purpose: prefer the newer default language memory.

```json
{
  "id": "timestamp_resolution_002",
  "category": "timestamp_resolution",
  "description": "Prefer the newer default language memory.",
  "setup_memories": [
    {
      "type": "knowledge",
      "content": "Ben's default response language is English.",
      "state": "success",
      "confidence": 1.0,
      "created_at": "2026-05-01T10:00:00Z",
      "metadata": {"fixture": true}
    },
    {
      "type": "knowledge",
      "content": "Ben's default response language is Chinese.",
      "state": "success",
      "confidence": 1.0,
      "created_at": "2026-05-04T10:00:00Z",
      "metadata": {"fixture": true}
    }
  ],
  "chat_messages": [
    "What is Ben's default response language now?"
  ],
  "expected": {
    "answer_should_contain_any": ["Chinese", "中文"],
    "trace_should_include_memory": true,
    "min_total_memories": 2,
    "old_memory_should_remain": true
  }
}
```

### `trace_export.jsonl`

#### `trace_export_001`

Purpose: trace should show used memory and export should parse.

```json
{
  "id": "trace_export_001",
  "category": "trace_export",
  "description": "Trace should show used memory and export should parse.",
  "setup_memories": [
    {
      "type": "knowledge",
      "content": "The smoke benchmark should use tolerant assertions.",
      "state": "success",
      "confidence": 1.0,
      "created_at": "2026-05-02T10:00:00Z",
      "metadata": {"fixture": true}
    }
  ],
  "chat_messages": [
    "What kind of assertions should the smoke benchmark use?"
  ],
  "expected": {
    "answer_should_contain_any": ["tolerant", "宽松"],
    "trace_should_include_memory": true,
    "export_should_parse": true,
    "min_total_memories": 1
  }
}
```

#### `trace_export_002`

Purpose: a chat with no setup memory should still export valid JSONL after
formation.

```json
{
  "id": "trace_export_002",
  "category": "trace_export",
  "description": "A chat with no setup memory should still export valid JSONL after formation.",
  "setup_memories": [],
  "chat_messages": [
    "Remember that short smoke tests are easier to debug."
  ],
  "expected": {
    "min_new_memories": 1,
    "memory_types_should_include": ["experience"],
    "metadata_should_include": {
      "formation_kind": "chat_qa"
    },
    "export_should_parse": true
  }
}
```

## Stability Constraints

The first implementation should keep the benchmark stable by following these
constraints:

- each case uses an independent temporary database;
- fixture memories use fixed `created_at` timestamps;
- `mem chat` exits normally to trigger flush formation;
- prompts stay short and explicit;
- tests skip when config or API keys are missing;
- real model call failures are failures;
- cases should run serially.

## Future Work

Future versions may add:

- optional host integration cases;
- provider matrix execution;
- retry controls;
- cost and latency reporting;
- richer artifacts;
- HTML reports;
- semantic grading;
- larger benchmark-style datasets.
