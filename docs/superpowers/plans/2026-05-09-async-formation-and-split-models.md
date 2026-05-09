# Async Formation and Split Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make local UI chat enqueue formation jobs for rolled session turns instead of waiting for formation, while preserving manual synchronous `Flush Session` and independent chat/formation model configuration.

**Architecture:** Add a small runtime formation job subsystem with JSON persistence, an in-memory queue, and one background worker thread. UI chat will use a new non-blocking chat helper that returns rolled turns; the server persists those turns as jobs and returns immediately after chat generation. Existing `Flush Session` remains synchronous and uses the configured formation model directly.

**Tech Stack:** Python standard library (`dataclasses`, `json`, `queue`, `threading`, `http.server`), existing `MemoryStore`, `SessionState`, `FormationService`, static HTML/CSS/JS, pytest.

---

## File Structure

- Create `memisalluneed/formation_jobs.py`
  - Defines `FormationJob`, `FormationJobStore`, `FormationWorker`, job status constants, and serialization helpers.
  - Owns local runtime job persistence in `.memisalluneed/formation_jobs.json`.
- Modify `memisalluneed/cli.py`
  - Add `ChatRunResult.rolled_turns`.
  - Keep existing CLI behavior: rolled turns are still formed synchronously for `mem chat`.
- Modify `memisalluneed/ui_server.py`
  - Add `job_store_path_for_state`.
  - Add `UIRuntime` that owns `FormationJobStore` and `FormationWorker`.
  - Add non-blocking `chat_send` path that enqueues rolled turns instead of forming them.
  - Add job list and retry handlers.
- Modify `memisalluneed/ui_static/index.html`
  - Add formation job panel inside the Chat tab.
- Modify `memisalluneed/ui_static/app.js`
  - Render job counts, recent jobs, errors, and retry buttons.
  - Poll jobs while the app is open and refresh after chat sends.
- Modify `memisalluneed/ui_static/styles.css`
  - Add compact job panel styling.
- Modify tests:
  - Add `tests/test_formation_jobs.py`.
  - Extend `tests/test_chat_cli.py`.
  - Extend `tests/test_ui_server.py`.
  - Existing config tests remain sufficient for independent model sections; add one explicit UI status assertion if needed.

---

### Task 1: Formation Job Data Model and Store

**Files:**
- Create: `memisalluneed/formation_jobs.py`
- Test: `tests/test_formation_jobs.py`

- [ ] **Step 1: Write failing tests for job serialization and store operations**

Create `tests/test_formation_jobs.py` with:

```python
from pathlib import Path

from memisalluneed.formation_jobs import FormationJob, FormationJobStore
from memisalluneed.session import SessionTurn


def make_turn(turn_id: str = "turn-1") -> SessionTurn:
    return SessionTurn(
        id=turn_id,
        user_message="remember this",
        assistant_message="stored",
        recalled_memory_ids=["memory-1"],
        created_at="2026-05-09T00:00:00+00:00",
    )


def test_formation_job_round_trips():
    job = FormationJob.new(session_id="session-1", turn=make_turn())

    loaded = FormationJob.from_dict(job.to_dict())

    assert loaded.id == job.id
    assert loaded.session_id == "session-1"
    assert loaded.turn.id == "turn-1"
    assert loaded.status == "pending"
    assert loaded.written_memory_ids == []
    assert loaded.error is None


def test_job_store_appends_and_lists_newest_first(tmp_path: Path):
    store = FormationJobStore(tmp_path / "formation_jobs.json")
    older = FormationJob.new(session_id="session-1", turn=make_turn("turn-1"))
    newer = FormationJob.new(session_id="session-1", turn=make_turn("turn-2"))

    store.append(older)
    store.append(newer)

    assert [job.turn.id for job in store.list()] == ["turn-2", "turn-1"]


def test_job_store_updates_status_and_error(tmp_path: Path):
    store = FormationJobStore(tmp_path / "formation_jobs.json")
    job = FormationJob.new(session_id="session-1", turn=make_turn())
    store.append(job)

    store.mark_running(job.id)
    assert store.get(job.id).status == "running"

    store.mark_failed(job.id, "The read operation timed out")
    failed = store.get(job.id)
    assert failed.status == "failed"
    assert failed.error == "The read operation timed out"

    store.reset_failed_to_pending(job.id)
    reset = store.get(job.id)
    assert reset.status == "pending"
    assert reset.error is None


def test_job_store_marks_written_with_memory_ids(tmp_path: Path):
    store = FormationJobStore(tmp_path / "formation_jobs.json")
    job = FormationJob.new(session_id="session-1", turn=make_turn())
    store.append(job)

    store.mark_written(job.id, ["memory-1", "memory-2"])

    written = store.get(job.id)
    assert written.status == "written"
    assert written.written_memory_ids == ["memory-1", "memory-2"]
    assert written.error is None


def test_job_store_recovers_running_jobs_as_pending(tmp_path: Path):
    store = FormationJobStore(tmp_path / "formation_jobs.json")
    job = FormationJob.new(session_id="session-1", turn=make_turn())
    store.append(job)
    store.mark_running(job.id)

    recovered = store.recover_interrupted_jobs()

    assert [job.id for job in recovered] == [job.id]
    assert store.get(job.id).status == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest pytest tests/test_formation_jobs.py -q
```

Expected: FAIL because `memisalluneed.formation_jobs` does not exist.

- [ ] **Step 3: Implement formation job model and JSON store**

Create `memisalluneed/formation_jobs.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from memisalluneed.schema import utc_now
from memisalluneed.session import SessionTurn

JOB_STATUSES = {"pending", "running", "written", "failed"}


@dataclass(frozen=True)
class FormationJob:
    id: str
    session_id: str
    turn: SessionTurn
    status: str
    written_memory_ids: list[str] = field(default_factory=list)
    error: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    @classmethod
    def new(cls, *, session_id: str, turn: SessionTurn) -> "FormationJob":
        now = utc_now()
        return cls(
            id=str(uuid4()),
            session_id=session_id,
            turn=turn,
            status="pending",
            created_at=now,
            updated_at=now,
        )

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "FormationJob":
        status = str(data["status"])
        if status not in JOB_STATUSES:
            raise ValueError(f"Invalid formation job status: {status}")
        turn = data["turn"]
        if not isinstance(turn, dict):
            raise ValueError("Formation job turn must be an object")
        return cls(
            id=str(data["id"]),
            session_id=str(data["session_id"]),
            turn=SessionTurn.from_dict(turn),
            status=status,
            written_memory_ids=[
                str(value) for value in data.get("written_memory_ids", [])
            ],
            error=None if data.get("error") is None else str(data.get("error")),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "turn": self.turn.to_dict(),
            "status": self.status,
            "written_memory_ids": list(self.written_memory_ids),
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class FormationJobStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, job: FormationJob) -> None:
        jobs = self._load()
        jobs.append(job)
        self._save(jobs)

    def list(self, *, limit: int | None = None) -> list[FormationJob]:
        jobs = sorted(self._load(), key=lambda job: job.created_at, reverse=True)
        if limit is not None:
            return jobs[:limit]
        return jobs

    def get(self, job_id: str) -> FormationJob:
        for job in self._load():
            if job.id == job_id:
                return job
        raise KeyError(f"Formation job not found: {job_id}")

    def mark_running(self, job_id: str) -> None:
        self._replace(job_id, status="running", error=None)

    def mark_written(self, job_id: str, memory_ids: list[str]) -> None:
        self._replace(
            job_id,
            status="written",
            written_memory_ids=list(memory_ids),
            error=None,
        )

    def mark_failed(self, job_id: str, error: str) -> None:
        self._replace(job_id, status="failed", error=error)

    def reset_failed_to_pending(self, job_id: str) -> FormationJob:
        job = self.get(job_id)
        if job.status != "failed":
            raise ValueError("Only failed formation jobs can be retried")
        self._replace(job_id, status="pending", error=None)
        return self.get(job_id)

    def recover_interrupted_jobs(self) -> list[FormationJob]:
        recovered: list[FormationJob] = []
        for job in self._load():
            if job.status == "running":
                self._replace(job.id, status="pending", error=None)
                recovered.append(self.get(job.id))
        return recovered

    def pending_jobs(self) -> list[FormationJob]:
        return [job for job in self._load() if job.status == "pending"]

    def _replace(self, job_id: str, **changes) -> None:
        jobs = []
        found = False
        for job in self._load():
            if job.id == job_id:
                data = job.to_dict()
                data.update(changes)
                data["updated_at"] = utc_now()
                job = FormationJob.from_dict(data)
                found = True
            jobs.append(job)
        if not found:
            raise KeyError(f"Formation job not found: {job_id}")
        self._save(jobs)

    def _load(self) -> list[FormationJob]:
        if not self.path.exists():
            return []
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Formation job file must contain a list")
        return [FormationJob.from_dict(item) for item in data if isinstance(item, dict)]

    def _save(self, jobs: list[FormationJob]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(
                [job.to_dict() for job in jobs],
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --with pytest pytest tests/test_formation_jobs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/formation_jobs.py tests/test_formation_jobs.py
git commit -m "Add formation job store"
```

---

### Task 2: Formation Worker

**Files:**
- Modify: `memisalluneed/formation_jobs.py`
- Test: `tests/test_formation_jobs.py`

- [ ] **Step 1: Write failing tests for worker success, failure, and retry queueing**

Append to `tests/test_formation_jobs.py`:

```python
from memisalluneed.formation_jobs import FormationWorker
from memisalluneed.schema import create_memory_item
from memisalluneed.store import MemoryStore


class FakeFormationModel:
    def __init__(self, response: str):
        self.response = response

    def complete(self, messages):
        return self.response


class FailingFormationModel:
    def complete(self, messages):
        raise RuntimeError("The read operation timed out")


def test_worker_processes_job_and_marks_written(tmp_path: Path):
    job_store = FormationJobStore(tmp_path / "formation_jobs.json")
    memory_store = MemoryStore(tmp_path / "memory.db")
    memory_store.init()
    recalled = create_memory_item("Existing recalled memory.")
    memory_store.add(recalled)
    turn = make_turn("turn-1")
    job = FormationJob.new(session_id="session-1", turn=turn)
    job_store.append(job)
    model = FakeFormationModel(
        """
{"memories":[{"type":"experience","content":"formed async memory","state":"success","confidence":0.8,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"session-1","turn_id":"turn-1","recalled_memory_ids":["memory-1"],"used_memory_ids":["memory-1"]}}]}
""".strip()
    )
    worker = FormationWorker(
        job_store=job_store,
        memory_store=memory_store,
        formation_model_factory=lambda: model,
    )

    worker.process_one(job)

    updated = job_store.get(job.id)
    assert updated.status == "written"
    assert len(updated.written_memory_ids) == 1
    assert memory_store.all()[0].content == "formed async memory"


def test_worker_marks_failed_on_exception(tmp_path: Path):
    job_store = FormationJobStore(tmp_path / "formation_jobs.json")
    memory_store = MemoryStore(tmp_path / "memory.db")
    memory_store.init()
    job = FormationJob.new(session_id="session-1", turn=make_turn())
    job_store.append(job)
    worker = FormationWorker(
        job_store=job_store,
        memory_store=memory_store,
        formation_model_factory=lambda: FailingFormationModel(),
    )

    worker.process_one(job)

    updated = job_store.get(job.id)
    assert updated.status == "failed"
    assert updated.error == "The read operation timed out"
    assert memory_store.all() == []


def test_worker_start_enqueues_pending_and_recovers_running(tmp_path: Path):
    job_store = FormationJobStore(tmp_path / "formation_jobs.json")
    memory_store = MemoryStore(tmp_path / "memory.db")
    memory_store.init()
    pending = FormationJob.new(session_id="session-1", turn=make_turn("turn-pending"))
    running = FormationJob.new(session_id="session-1", turn=make_turn("turn-running"))
    job_store.append(pending)
    job_store.append(running)
    job_store.mark_running(running.id)
    worker = FormationWorker(
        job_store=job_store,
        memory_store=memory_store,
        formation_model_factory=lambda: FakeFormationModel('{"memories":[]}'),
    )

    worker.enqueue_startup_jobs()

    assert worker.queue_size() == 2
    assert job_store.get(running.id).status == "pending"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest pytest tests/test_formation_jobs.py::test_worker_processes_job_and_marks_written tests/test_formation_jobs.py::test_worker_marks_failed_on_exception tests/test_formation_jobs.py::test_worker_start_enqueues_pending_and_recovers_running -q
```

Expected: FAIL because `FormationWorker` does not exist.

- [ ] **Step 3: Implement `FormationWorker`**

Append to `memisalluneed/formation_jobs.py`:

```python
import queue
import threading
from collections.abc import Callable

from memisalluneed.formation import FormationService
from memisalluneed.models.base import ChatModel
from memisalluneed.store import MemoryStore


class FormationWorker:
    def __init__(
        self,
        *,
        job_store: FormationJobStore,
        memory_store: MemoryStore,
        formation_model_factory: Callable[[], ChatModel],
    ) -> None:
        self.job_store = job_store
        self.memory_store = memory_store
        self.formation_model_factory = formation_model_factory
        self._queue: queue.Queue[str] = queue.Queue()
        self._thread: threading.Thread | None = None

    def enqueue(self, job: FormationJob) -> None:
        self._queue.put(job.id)

    def enqueue_startup_jobs(self) -> None:
        for job in self.job_store.recover_interrupted_jobs():
            self.enqueue(job)
        for job in self.job_store.pending_jobs():
            self.enqueue(job)

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self.enqueue_startup_jobs()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def queue_size(self) -> int:
        return self._queue.qsize()

    def process_one(self, job: FormationJob) -> None:
        self.job_store.mark_running(job.id)
        try:
            model = self.formation_model_factory()
            formation = FormationService(model=model, store=self.memory_store)
            recalled_memories = [
                memory
                for memory_id in job.turn.recalled_memory_ids
                if (memory := self.memory_store.get(memory_id)) is not None
            ]
            written = formation.form_from_chat_qa_turn(
                session_id=job.session_id,
                turn=job.turn,
                recalled_memories=recalled_memories,
            )
            self.job_store.mark_written(job.id, [memory.id for memory in written])
        except Exception as error:
            self.job_store.mark_failed(job.id, str(error))

    def _run(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                job = self.job_store.get(job_id)
                if job.status == "pending":
                    self.process_one(job)
            finally:
                self._queue.task_done()
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
uv run --with pytest pytest tests/test_formation_jobs.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add memisalluneed/formation_jobs.py tests/test_formation_jobs.py
git commit -m "Add formation worker"
```

---

### Task 3: Non-Blocking UI Chat Roll Enqueue

**Files:**
- Modify: `memisalluneed/cli.py`
- Modify: `memisalluneed/ui_server.py`
- Test: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing UI tests for rolled job enqueue and no formation wait**

Append to `tests/test_ui_server.py`:

```python
class ExplodingFormationModel:
    def complete(self, messages):
        raise AssertionError("formation model should not run on chat send")


def test_chat_send_enqueues_rolled_turn_without_running_formation(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text("placeholder", encoding="utf-8")
    state = UIState(db_path=tmp_path / "memory.db", config_path=config_path)
    config = AppConfig(
        chat_model=ModelRoleConfig(provider="openai", model="chat"),
        formation_model=ModelRoleConfig(provider="openai", model="formation"),
        session=SessionConfig(
            max_turns=1,
            max_tokens=100000,
            recall_top_k=1,
            recall_candidate_k=1,
        ),
        http=HttpConfig(request_timeout=60),
        providers={
            "openai": ProviderConfig(
                api_key_env="OPENAI_API_KEY",
                base_url="https://example.test/v1",
            )
        },
    )
    session_path = tmp_path / ".memisalluneed" / "session.json"
    session_path.parent.mkdir()
    session_path.write_text(
        """
{
  "session_id": "session-1",
  "created_at": "2026-05-09T00:00:00+00:00",
  "updated_at": "2026-05-09T00:00:00+00:00",
  "turns": [
    {
      "id": "old-turn",
      "user_message": "old",
      "assistant_message": "old answer",
      "recalled_memory_ids": [],
      "created_at": "2026-05-09T00:00:00+00:00"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("memisalluneed.ui_server.load_config", lambda path: config)
    monkeypatch.setattr(
        "memisalluneed.ui_server.model_from_config",
        lambda config, role: FakeReplyModel()
        if role.model == "chat"
        else ExplodingFormationModel(),
    )

    response = chat_send(state, "new message")

    assert response["assistant_reply"] == "assistant reply"
    assert response["written_memories"] == []
    assert response["formation_jobs"][0]["turn_id"] == "old-turn"
    assert response["formation_jobs"][0]["status"] == "pending"
    assert MemoryStore(state.db_path).all() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest pytest tests/test_ui_server.py::test_chat_send_enqueues_rolled_turn_without_running_formation -q
```

Expected: FAIL because `chat_send` does not return `formation_jobs` and current `run_chat_once` synchronously forms rolled turns.

- [ ] **Step 3: Add a `form_rolled` switch and `rolled_turns` to `run_chat_once`**

Modify the `ChatRunResult` dataclass in `memisalluneed/cli.py` to:

```python
@dataclass(frozen=True)
class ChatRunResult:
    assistant_reply: str
    used_memories: list
    rolled_turns: list[SessionTurn] = field(default_factory=list)
```

Add `field` to the existing dataclass import:

```python
from dataclasses import dataclass, field
```

Add a keyword parameter to `run_chat_once`:

```python
def run_chat_once(
    *,
    user_message: str,
    config: AppConfig,
    store: MemoryStore,
    session_path: str | Path,
    chat_model: ChatModel,
    formation_model: ChatModel,
    resume: bool = True,
    form_rolled: bool = True,
) -> ChatRunResult:
```

Wrap the existing synchronous formation block:

```python
    if form_rolled:
        formation = FormationService(model=formation_model, store=store)
        for rolled_turn in rolled_turns:
            recalled_memories = [
                memory
                for memory_id in rolled_turn.recalled_memory_ids
                if (memory := store.get(memory_id)) is not None
            ]
            formation.form_from_chat_qa_turn(
                session_id=session.session_id,
                turn=rolled_turn,
                recalled_memories=recalled_memories,
            )
```

Remove the old unconditional `formation = FormationService(...)` and `for rolled_turn in rolled_turns:` block. Keep `session.save(session_path)` after the conditional.

Return rolled turns:

```python
    return ChatRunResult(
        assistant_reply=assistant_reply,
        used_memories=used_memories,
        rolled_turns=rolled_turns,
    )
```

- [ ] **Step 4: Add a UI-only non-blocking chat helper**

In `memisalluneed/ui_server.py`, add imports near existing imports:

```python
from memisalluneed.formation_jobs import FormationJob, FormationJobStore
```

Add helper paths and response serializer:

```python
def job_store_path_for_state(state: UIState) -> Path:
    return session_path_for_state(state).with_name("formation_jobs.json")


def job_to_response(job) -> dict[str, object]:
    return {
        "id": job.id,
        "turn_id": job.turn.id,
        "status": job.status,
        "written_memory_ids": list(job.written_memory_ids),
        "error": job.error,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
```

Replace the current `chat_send` `result = chat_once(...)` block through the return statement with:

```python
    result = chat_once(
        user_message=message,
        config=config,
        store=store_for_state(state),
        session_path=session_path_for_state(state),
        chat_model=model_from_config(config, config.chat_model),
        formation_model=model_from_config(config, config.formation_model),
        resume=resume,
        form_rolled=False,
    )
    job_store = FormationJobStore(job_store_path_for_state(state))
    jobs = []
    for turn in result.rolled_turns:
        job = FormationJob.new(session_id=SessionState.load(session_path_for_state(state)).session_id, turn=turn)
        job_store.append(job)
        jobs.append(job)
    return {
        "assistant_reply": result.assistant_reply,
        "used_memories": [memory_to_response(memory) for memory in result.used_memories],
        "written_memories": [],
        "formation_jobs": [job_to_response(job) for job in jobs],
    }
```

This is an intermediate implementation. Task 4 will replace the append-only behavior with worker enqueueing through `UIRuntime`.

- [ ] **Step 5: Run focused test**

Run:

```bash
uv run --with pytest pytest tests/test_ui_server.py::test_chat_send_enqueues_rolled_turn_without_running_formation -q
```

Expected: PASS.

- [ ] **Step 6: Run existing UI tests**

Run:

```bash
uv run --with pytest pytest tests/test_ui_server.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add memisalluneed/cli.py memisalluneed/ui_server.py tests/test_ui_server.py
git commit -m "Enqueue rolled UI turns as formation jobs"
```

---

### Task 4: UI Runtime Worker and Retry API

**Files:**
- Modify: `memisalluneed/ui_server.py`
- Test: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing tests for job list and retry APIs**

Append to `tests/test_ui_server.py`:

```python
from memisalluneed.formation_jobs import FormationJob, FormationJobStore
from memisalluneed.session import SessionTurn


def make_ui_job(tmp_path: Path, status: str = "failed") -> FormationJob:
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")
    turn = SessionTurn(
        id="turn-1",
        user_message="hello",
        assistant_message="reply",
        recalled_memory_ids=[],
        created_at="2026-05-09T00:00:00+00:00",
    )
    job = FormationJob.new(session_id="session-1", turn=turn)
    store = FormationJobStore(job_store_path_for_state(state))
    store.append(job)
    if status == "failed":
        store.mark_failed(job.id, "failed once")
    return store.get(job.id)


def test_list_formation_jobs_returns_stable_shape(tmp_path: Path):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")
    job = make_ui_job(tmp_path, status="failed")

    response = list_formation_jobs(state)

    assert response["jobs"][0]["id"] == job.id
    assert response["jobs"][0]["turn_id"] == "turn-1"
    assert response["jobs"][0]["status"] == "failed"
    assert response["jobs"][0]["error"] == "failed once"


def test_retry_failed_formation_job_resets_to_pending(tmp_path: Path):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")
    job = make_ui_job(tmp_path, status="failed")

    response = retry_formation_job(state, job.id)

    assert response["job"]["status"] == "pending"
    assert response["job"]["error"] is None
```

Add missing imports at the top of `tests/test_ui_server.py`:

```python
from memisalluneed.ui_server import job_store_path_for_state
from memisalluneed.ui_server import list_formation_jobs, retry_formation_job
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --with pytest pytest tests/test_ui_server.py::test_list_formation_jobs_returns_stable_shape tests/test_ui_server.py::test_retry_failed_formation_job_resets_to_pending -q
```

Expected: FAIL because `list_formation_jobs` and `retry_formation_job` do not exist.

- [ ] **Step 3: Implement UI job list and retry helpers**

In `memisalluneed/ui_server.py`, add:

```python
def job_store_for_state(state: UIState) -> FormationJobStore:
    return FormationJobStore(job_store_path_for_state(state))


def list_formation_jobs(state: UIState, *, limit: int = 20) -> dict[str, object]:
    return {
        "jobs": [
            job_to_response(job)
            for job in job_store_for_state(state).list(limit=limit)
        ]
    }


def retry_formation_job(state: UIState, job_id: str) -> dict[str, object]:
    job = job_store_for_state(state).reset_failed_to_pending(job_id)
    return {"job": job_to_response(job)}
```

- [ ] **Step 4: Wire GET and POST routes**

In `create_handler.do_GET`, add before the `else: super().do_GET()` branch:

```python
                elif parsed.path == "/api/formation/jobs":
                    self.send_json(
                        list_formation_jobs(
                            state,
                            limit=int(query.get("limit", ["20"])[0]),
                        )
                    )
```

In `create_handler.do_POST`, add before the final unsupported route:

```python
                elif self.path.startswith("/api/formation/jobs/") and self.path.endswith("/retry"):
                    job_id = self.path.split("/")[-2]
                    self.send_json(retry_formation_job(state, job_id))
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run --with pytest pytest tests/test_ui_server.py::test_list_formation_jobs_returns_stable_shape tests/test_ui_server.py::test_retry_failed_formation_job_resets_to_pending -q
```

Expected: PASS.

- [ ] **Step 6: Add runtime worker enqueueing**

In `memisalluneed/ui_server.py`, add:

```python
from dataclasses import dataclass, field
from memisalluneed.formation_jobs import FormationWorker
```

Extend imports carefully if `dataclass` is already imported; add `field` to the same import line.

Add:

```python
@dataclass
class UIRuntime:
    state: UIState
    worker: FormationWorker | None = None

    def start(self) -> None:
        if self.worker is not None:
            self.worker.start()

    def enqueue(self, job) -> None:
        if self.worker is not None:
            self.worker.enqueue(job)
```

In `serve_ui`, construct and start a worker:

```python
def serve_ui(state: UIState, *, host: str, port: int) -> None:
    config = load_config(state.config_path)
    worker = FormationWorker(
        job_store=job_store_for_state(state),
        memory_store=store_for_state(state),
        formation_model_factory=lambda: model_from_config(config, config.formation_model),
    )
    runtime = UIRuntime(state=state, worker=worker)
    runtime.start()
    server = ThreadingHTTPServer((host, port), create_handler(state, runtime=runtime))
    print(f"MEMisALLuNEED UI running at http://{host}:{port}")
    server.serve_forever()
```

Change `create_handler` signature:

```python
def create_handler(state: UIState, runtime: UIRuntime | None = None):
```

In `chat_send`, add optional runtime parameter and enqueue jobs:

```python
def chat_send(
    state: UIState,
    message: str,
    *,
    resume: bool = True,
    runtime: UIRuntime | None = None,
) -> dict[str, Any]:
```

When each job is appended:

```python
        if runtime is not None:
            runtime.enqueue(job)
```

In `do_POST` for `/api/chat/send`, pass runtime:

```python
                    self.send_json(
                        chat_send(
                            state,
                            str(payload.get("message", "")),
                            runtime=runtime,
                        )
                    )
```

In `retry_formation_job`, accept optional runtime:

```python
def retry_formation_job(
    state: UIState,
    job_id: str,
    *,
    runtime: UIRuntime | None = None,
) -> dict[str, object]:
    job = job_store_for_state(state).reset_failed_to_pending(job_id)
    if runtime is not None:
        runtime.enqueue(job)
    return {"job": job_to_response(job)}
```

Pass runtime from the retry route:

```python
                    self.send_json(retry_formation_job(state, job_id, runtime=runtime))
```

- [ ] **Step 7: Run full UI server tests**

Run:

```bash
uv run --with pytest pytest tests/test_ui_server.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add memisalluneed/ui_server.py tests/test_ui_server.py
git commit -m "Add UI formation job APIs and runtime"
```

---

### Task 5: Frontend Formation Job Panel

**Files:**
- Modify: `memisalluneed/ui_static/index.html`
- Modify: `memisalluneed/ui_static/app.js`
- Modify: `memisalluneed/ui_static/styles.css`
- Test: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing static asset test for job panel hooks**

Append to `tests/test_ui_server.py`:

```python
def test_static_assets_include_formation_job_panel_hooks():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    app_js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert 'id="formation-jobs"' in html
    assert 'id="formation-job-counts"' in html
    assert "loadFormationJobs" in app_js
    assert "retryFormationJob" in app_js
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --with pytest pytest tests/test_ui_server.py::test_static_assets_include_formation_job_panel_hooks -q
```

Expected: FAIL because the panel hooks are not present.

- [ ] **Step 3: Add HTML panel**

In `memisalluneed/ui_static/index.html`, inside the Chat tab near the existing used memories block, add:

```html
          <section class="formation-panel">
            <div class="section-header">
              <h2>Formation Jobs</h2>
              <button id="refresh-formation-jobs" type="button">Refresh</button>
            </div>
            <div id="formation-job-counts" class="job-counts"></div>
            <div id="formation-jobs" class="job-list"></div>
          </section>
```

- [ ] **Step 4: Add frontend job rendering and retry**

In `memisalluneed/ui_static/app.js`, add after `searchMemories`:

```javascript
function summarizeJobs(jobs) {
  const counts = {pending: 0, running: 0, written: 0, failed: 0};
  for (const job of jobs) {
    counts[job.status] = (counts[job.status] || 0) + 1;
  }
  return counts;
}

function renderFormationJobs(jobs) {
  const counts = summarizeJobs(jobs);
  document.querySelector("#formation-job-counts").textContent =
    `pending=${counts.pending} running=${counts.running} written=${counts.written} failed=${counts.failed}`;
  const list = document.querySelector("#formation-jobs");
  list.innerHTML = "";
  for (const job of jobs) {
    const row = document.createElement("div");
    row.className = `job-row ${job.status}`;
    const error = job.error ? ` error=${job.error}` : "";
    row.innerHTML = `<div>${job.turn_id} ${job.status} written=${job.written_memory_ids.length}${error}</div>`;
    if (job.status === "failed") {
      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Retry";
      button.addEventListener("click", () => retryFormationJob(job.id).catch(showError));
      row.appendChild(button);
    }
    list.appendChild(row);
  }
}

async function loadFormationJobs() {
  const data = await requestJson("/api/formation/jobs?limit=20");
  renderFormationJobs(data.jobs);
}

async function retryFormationJob(jobId) {
  clearError();
  await requestJson(`/api/formation/jobs/${jobId}/retry`, {method: "POST"});
  await loadFormationJobs();
}
```

In `sendChat`, after `await loadMemories();`, add:

```javascript
  await loadFormationJobs();
```

In `postSessionAction`, after `await loadMemories();`, add:

```javascript
  await loadFormationJobs();
```

In `main`, add event listener and initial/poll loading:

```javascript
  document.querySelector("#refresh-formation-jobs").addEventListener("click", () => loadFormationJobs().catch(showError));
  await loadFormationJobs();
  setInterval(() => loadFormationJobs().catch(showError), 3000);
```

- [ ] **Step 5: Add CSS**

Append to `memisalluneed/ui_static/styles.css`:

```css
.formation-panel {
  margin-top: 16px;
}

.section-header {
  align-items: center;
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.job-counts {
  color: #555;
  font-size: 13px;
  margin-bottom: 8px;
}

.job-list {
  display: grid;
  gap: 6px;
}

.job-row {
  align-items: center;
  border: 1px solid #ddd;
  border-radius: 6px;
  display: flex;
  font-size: 13px;
  justify-content: space-between;
  padding: 8px;
}

.job-row.failed {
  border-color: #d66;
}

.job-row.written {
  border-color: #6a8;
}
```

- [ ] **Step 6: Run static asset test**

Run:

```bash
uv run --with pytest pytest tests/test_ui_server.py::test_static_assets_include_formation_job_panel_hooks -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add memisalluneed/ui_static/index.html memisalluneed/ui_static/app.js memisalluneed/ui_static/styles.css tests/test_ui_server.py
git commit -m "Show formation jobs in local UI"
```

---

### Task 6: Split Model Configuration Documentation and Status Coverage

**Files:**
- Modify: `config.example.toml`
- Modify: `tests/test_ui_server.py`

- [ ] **Step 1: Write or update status test for independent model readiness**

In `tests/test_ui_server.py`, update `test_build_status_reports_required_api_key_names_and_presence` so it continues to assert different providers and API key readiness:

```python
    assert status["models"]["chat"]["provider"] == "openai"
    assert status["models"]["chat"]["api_key_env"] == "OPENAI_API_KEY"
    assert status["models"]["chat"]["api_key_set"] is False
    assert status["models"]["formation"]["provider"] == "qwen"
    assert status["models"]["formation"]["api_key_env"] == "QWEN_API_KEY"
    assert status["models"]["formation"]["api_key_set"] is True
```

- [ ] **Step 2: Add config example comments**

In `config.example.toml`, add comments above `[formation_model]`:

```toml
# The formation model can be a faster or cheaper model than the chat model.
# It only needs to produce structured memory JSON.
[formation_model]
```

Keep the existing model name. Do not invent a new SiliconFlow model.

- [ ] **Step 3: Run config/status tests**

Run:

```bash
uv run --with pytest pytest tests/test_config.py tests/test_ui_server.py::test_build_status_reports_required_api_key_names_and_presence -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add config.example.toml tests/test_ui_server.py
git commit -m "Document split chat and formation models"
```

---

### Task 7: Full Verification

**Files:**
- No code files unless previous tasks reveal a defect.

- [ ] **Step 1: Run full test suite**

Run:

```bash
uv run --with pytest --with httpx pytest -q
```

Expected:

```text
... passed, 8 skipped
```

The exact passed count may increase because this plan adds tests.

- [ ] **Step 2: Manually verify UI startup**

Run:

```bash
uv run --env-file .env mem ui --config .memisalluneed/config.toml --db memory.db --port 8766
```

Expected:

```text
MEMisALLuNEED UI running at http://127.0.0.1:8766
```

If port `8766` is occupied, rerun with:

```bash
uv run --env-file .env mem ui --config .memisalluneed/config.toml --db memory.db --port 8767
```

- [ ] **Step 3: Manually verify behavior in browser**

Use the UI:

1. Send one normal chat message while the active session has not exceeded `max_turns`.
2. Confirm `Formation Jobs` shows no new job.
3. Send enough short messages to exceed `max_turns`.
4. Confirm `Formation Jobs` shows `pending` or `running`, then `written` or `failed`.
5. If a job fails, click `Retry` and confirm the status returns to `pending` or progresses.
6. Click `Flush Session` and confirm the response still writes memories synchronously.

- [ ] **Step 4: Stop the server**

Use `Ctrl-C` in the terminal where `mem ui` is running.

- [ ] **Step 5: Check worktree status**

Run:

```bash
git status --short
```

Expected: no output.

- [ ] **Step 6: Commit verification-only fixes if needed**

Only if verification revealed small fixes, commit them:

```bash
git add <changed-files>
git commit -m "Fix async formation verification issues"
```

If no fixes were needed, do not create a commit.

---

## Self-Review Notes

- Spec coverage:
  - Background jobs: Tasks 1, 2, 4, 5.
  - Chat send non-blocking behavior: Task 3.
  - Manual synchronous flush: Tasks 3, 4, 7 preserve and test existing behavior.
  - Retry failed jobs: Tasks 1, 2, 4, 5.
  - Split chat/formation config: Task 6.
  - UI job display and polling: Task 5.
- No new `formation_turns` setting is introduced.
- No new default formation model name is chosen.
- Job state is stored in `.memisalluneed/formation_jobs.json`, not the memory table.
- The plan intentionally leaves CLI `mem chat` synchronous for rolled formation; the spec targets local UI responsiveness.
