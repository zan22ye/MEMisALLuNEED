# Current Project Risks

Date: 2026-05-09

## Risks

1. Formation job storage is not safe under concurrent access. The UI server can handle multiple request threads while the background formation worker also reads and writes the same JSON job file, so jobs can be lost, overwritten, or persisted as corrupted JSON.

2. Manual session flush and background formation jobs can race. A turn with a pending or running formation job can also be synchronously flushed, which can create duplicate memories for the same chat turn.

3. UI API error responses collapse unrelated failures into HTTP 400. User input errors, missing resources, model timeouts, missing API keys, corrupted local files, SQLite failures, and internal bugs can all appear as bad requests.

4. Session and formation job JSON files are written non-atomically. If the process exits or is interrupted during a write, the next load can see a partially written JSON file.

5. SQLite access is not tuned for concurrent local UI usage. The store opens plain SQLite connections without an explicit busy timeout or WAL mode, so simultaneous UI, CLI, and background worker access can be more likely to hit database lock failures.

6. Long-running UI usage can leak HTTP client resources. OpenAI-compatible model clients create `httpx.Client` instances, but the current model abstraction does not expose a lifecycle for closing or reusing those clients cleanly.

7. `cli.py` and `ui_server.py` have grown into broad orchestration modules. They now mix command parsing, HTTP routing, business operations, session control, model construction, and formation coordination, which raises the risk of future changes causing unrelated regressions.

8. Test coverage does not yet exercise the highest-risk local runtime failures. Current tests cover many happy paths, but do not cover concurrent job writes, flush-vs-background formation races, partially written JSON files, corrupted session/job files, or SQLite lock behavior.
