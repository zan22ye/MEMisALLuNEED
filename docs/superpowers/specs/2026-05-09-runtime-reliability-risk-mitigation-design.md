# Runtime Reliability Risk Mitigation Design

Date: 2026-05-09

## Goal

Mitigate the highest-priority local runtime reliability risks in the current CLI/UI memory system.

The focus is data safety, idempotent memory formation, clearer UI errors, SQLite local concurrency, HTTP client cleanup, and tests for failure-prone runtime paths. This spec does not include broad structural refactoring of `cli.py` or `ui_server.py`.

## Current Risks

This design is based on `docs/current-risks.md`.

The risks addressed in this phase are:

1. Formation job JSON storage is unsafe under concurrent access.
2. Manual session flush and background formation jobs can duplicate memories for the same turn.
3. UI API errors collapse unrelated failures into HTTP 400.
4. Session and formation job JSON files are written non-atomically.
5. SQLite access is not tuned for concurrent local UI usage.
6. OpenAI-compatible HTTP clients do not have a clear cleanup path.
7. High-risk runtime failure modes are not covered by tests.

The broad module-size risk in `cli.py` and `ui_server.py` is acknowledged but intentionally not fixed in this phase.

## Scope

In scope:

- Add safe JSON file helpers.
- Use atomic JSON writes for session and formation job files.
- Add process-local locking to `FormationJobStore`.
- Prevent duplicate memory formation across manual flush and background formation jobs.
- Improve UI HTTP error mapping while keeping the current handler structure.
- Enable SQLite timeout, busy timeout, and WAL for local memory storage.
- Use short-lived HTTP clients for model calls created by `OpenAICompatibleChatModel`.
- Add focused tests for concurrency, atomic writes, formation idempotency, SQLite settings, and one lightweight UI-to-worker formation flow.

Out of scope:

- Migrating formation jobs to SQLite.
- Introducing a full formation ledger.
- Adding database schema migrations.
- Adding a SQLite embedding column.
- Adding vector search, external search services, or persistent BM25 indexes.
- Designing global reusable model clients or UI server shutdown lifecycle.
- Splitting `cli.py` into `chat_service.py`.
- Splitting `ui_server.py` into separate action and HTTP modules.
- Real-model tests for these reliability paths.

## Design Decisions

### 1. Formation Job Store Safety

Use a process-local lock plus atomic JSON writes.

`FormationJobStore` should own a `threading.RLock` and use it around all operations that load, inspect, modify, or save jobs:

- `append`
- `list`
- `get`
- `mark_running`
- `mark_written`
- `mark_failed`
- `reset_failed_to_pending`
- `recover_interrupted_jobs`
- `pending_jobs`

The lock protects concurrent access inside one `mem ui` process, where request threads and the background worker can update `formation_jobs.json` at the same time.

The store should save through the shared atomic JSON writer described below. This reduces the chance of corrupted job JSON if the process is interrupted during a write.

Trade-off:

- This does not protect against two separate `mem ui` processes writing the same job file.
- It is intentionally smaller than moving jobs to SQLite.

### 2. Atomic JSON File Helpers

Add a small JSON file helper module, for example:

```text
memisalluneed/file_io.py
```

Required functions:

```python
read_json(path: str | Path) -> object
write_json_atomic(path: str | Path, value: object) -> None
```

`write_json_atomic` should:

- create the parent directory;
- write JSON to a temporary file in the same directory;
- use `ensure_ascii=False`, `indent=2`, and `sort_keys=True`;
- replace the target with `os.replace`.

Consumers:

- `SessionState.save`
- `FormationJobStore._save`

Trade-off:

- This prevents partially written JSON files from replacing valid files.
- It does not solve logical concurrent updates by itself; `FormationJobStore` still needs its lock.

### 3. Flush And Background Formation Idempotency

Use the selected A+B approach.

Manual flush should skip turns that already have a relevant formation job.

When `flush_session` or its helper enumerates session turns, it should skip a turn if either condition is true:

- a memory already exists with metadata identifying that chat turn as formed;
- `formation_jobs.json` contains a job for the same turn with status `pending`, `running`, or `written`.

Background worker processing should also perform a turn-level idempotency check immediately before formation work. If memory already exists for that turn, the worker should not call the formation model or write duplicate memories.

Expected behavior:

- pending/running/written job means manual flush does not form that turn again;
- already-formed turn means background worker does not form that turn again;
- failed jobs remain retryable through the existing retry path.

Trade-off:

- A stuck pending job can cause flush to skip that turn until the user retries or clears the job state.
- This is still lighter than a full formation ledger.

### 4. UI Error Mapping

Keep the current handler structure, but add exception-to-response mapping.

Add a helper such as:

```python
error_response_for_exception(error: Exception) -> tuple[int, str, str]
```

Expected mappings:

- `json.JSONDecodeError` -> HTTP 400
- `ValueError` -> HTTP 400
- `KeyError` -> HTTP 404
- missing API key runtime error -> HTTP 503
- `httpx.TimeoutException` -> HTTP 504
- `httpx.HTTPStatusError` -> HTTP 502
- `sqlite3.Error` -> HTTP 500
- unknown exception -> HTTP 500

`do_GET` and `do_POST` should use this helper instead of returning HTTP 400 for every exception.

Trade-off:

- This keeps the change small and improves diagnosis quickly.
- It still relies on existing exception types and does not introduce project-level exception classes.

### 5. SQLite Local Concurrency Settings

Tune `MemoryStore` for local UI usage.

`MemoryStore._connect()` should use a nonzero timeout:

```python
sqlite3.connect(self.db_path, timeout=30)
```

`MemoryStore.init()` should configure:

```sql
PRAGMA busy_timeout = 30000;
PRAGMA journal_mode = WAL;
```

Expected behavior:

- transient write locks are less likely to fail immediately;
- UI reads and background writes have better local concurrency characteristics.

Trade-off:

- SQLite will create `memory.db-wal` and `memory.db-shm` files next to the database.
- WAL is intended for local filesystem usage and may be unsuitable for some network filesystems.

### 6. Short-Lived HTTP Clients

Use short-lived HTTP clients for model instances that create their own client.

`OpenAICompatibleChatModel` should continue supporting injected `httpx.Client` instances for tests or advanced callers. When no client is injected, model calls should create a short-lived client and close it after the request.

Expected behavior:

- model calls do not leave self-created `httpx.Client` instances open indefinitely;
- tests can still inject a fake or controlled client;
- no UI-wide model lifecycle or shutdown hook is required in this phase.

Trade-off:

- Connection reuse is reduced.
- This favors reliability and resource cleanup over request throughput for the current local UI.

### 7. Runtime Reliability Tests

Add focused tests for the selected reliability behavior.

Required unit coverage:

- `FormationJobStore` preserves jobs under concurrent append calls.
- `FormationJobStore` does not overwrite status updates under concurrent read-modify-write operations.
- atomic JSON write preserves the previous valid file if replacement preparation fails.
- `SessionState.save` uses atomic JSON writing.
- `FormationJobStore._save` uses atomic JSON writing.
- manual flush skips turns with pending, running, or written formation jobs.
- worker skips formation when the turn already has formed memory.
- `MemoryStore.init` enables WAL.
- `MemoryStore` connections expose a busy timeout.
- UI error mapping returns distinct statuses for bad JSON, not found, missing API key, timeout, upstream HTTP error, SQLite error, and unknown error.
- self-created HTTP clients are closed after model calls.

Required lightweight integration coverage:

- UI chat rolls an old turn out of the active session;
- the rolled turn creates a pending formation job;
- a worker processes that job with a fake model;
- the job becomes `written`;
- the formed memory appears in `memory.db`.

Tests should use fake models and local temporary files only. They should not call real model providers.

## Non-Goals

This phase does not restructure broad modules.

`cli.py` and `ui_server.py` are known to be too broad, but this phase should not move `run_chat_once`, HTTP routing, or UI action helpers into new modules unless a very small extraction is required to complete one of the reliability fixes above.

This phase also does not implement a formation ledger. The chosen idempotency approach is intentionally smaller: flush checks job state, and worker checks turn-level memory formation before writing.

## Acceptance Criteria

- Existing CLI, UI, chat, and formation behavior remains user-compatible.
- Formation job JSON updates are protected by a process-local lock and atomic writes.
- Session JSON saves use atomic writes.
- Manual flush does not duplicate formation for turns with pending, running, or written jobs.
- Background formation worker does not duplicate formation for turns already written by another path.
- UI API no longer reports all internal failures as HTTP 400.
- SQLite memory storage uses timeout, busy timeout, and WAL.
- Self-created model HTTP clients are closed after use.
- Focused reliability tests pass.
- Full non-real-model test suite passes.
