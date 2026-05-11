from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest

from memisalluneed.config import ProviderConfig
from memisalluneed.file_io import read_json, write_json_atomic
from memisalluneed.formation_jobs import FormationJob, FormationJobStore, FormationWorker
from memisalluneed.models.openai_compatible import OpenAICompatibleChatModel
from memisalluneed.schema import create_memory_item
from memisalluneed.session import SessionState, SessionTurn
from memisalluneed.store import MemoryStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_turn(turn_id: str = "turn-1") -> SessionTurn:
    return SessionTurn(
        id=turn_id,
        user_message="remember this",
        assistant_message="stored",
        recalled_memory_ids=[],
        created_at="2026-05-09T00:00:00+00:00",
    )


def make_job_store(tmp_path: Path) -> FormationJobStore:
    return FormationJobStore(tmp_path / "formation_jobs.json")


# ---------------------------------------------------------------------------
# Task 1: Atomic JSON helpers
# ---------------------------------------------------------------------------


def test_write_json_atomic_preserves_previous_file_if_replace_fails(tmp_path: Path):
    target = tmp_path / "data.json"
    target.write_text(json.dumps({"old": True}), encoding="utf-8")

    with patch("memisalluneed.file_io.os.replace", side_effect=OSError("disk full")):
        with pytest.raises(OSError, match="disk full"):
            write_json_atomic(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}


def test_session_state_save_uses_atomic_write(tmp_path: Path):
    session_path = tmp_path / "session.json"
    session = SessionState.new()

    with patch("memisalluneed.session.write_json_atomic") as mock_write:
        session.save(session_path)

    mock_write.assert_called_once()
    args = mock_write.call_args[0]
    assert Path(args[0]) == session_path
    assert args[1]["session_id"] == session.session_id


# ---------------------------------------------------------------------------
# Task 2: Formation job store atomic save
# ---------------------------------------------------------------------------


def test_formation_job_store_save_uses_atomic_write(tmp_path: Path):
    store = make_job_store(tmp_path)
    job = FormationJob.new(session_id="s", turn=make_turn())

    with patch("memisalluneed.formation_jobs.write_json_atomic") as mock_write:
        store.append(job)

    mock_write.assert_called_once()
    args = mock_write.call_args[0]
    assert Path(args[0]) == store.path
    assert isinstance(args[1], list)
    assert args[1][0]["id"] == job.id


# ---------------------------------------------------------------------------
# Task 3: FormationJobStore concurrency lock
# ---------------------------------------------------------------------------


def test_formation_job_store_concurrent_appends_preserve_all_jobs(tmp_path: Path):
    store = make_job_store(tmp_path)
    errors: list[Exception] = []

    def append_job(turn_id: str) -> None:
        try:
            store.append(FormationJob.new(session_id="s", turn=make_turn(turn_id)))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=append_job, args=(f"turn-{i}",)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(store.list()) == 20


def test_formation_job_store_concurrent_status_updates_do_not_lose_jobs(tmp_path: Path):
    store = make_job_store(tmp_path)
    jobs = [FormationJob.new(session_id="s", turn=make_turn(f"t{i}")) for i in range(10)]
    for job in jobs:
        store.append(job)

    errors: list[Exception] = []

    def mark_running(job_id: str) -> None:
        try:
            store.mark_running(job_id)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=mark_running, args=(j.id,)) for j in jobs]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    statuses = {store.get(j.id).status for j in jobs}
    assert statuses == {"running"}


# ---------------------------------------------------------------------------
# Task 4: SQLite concurrency settings
# ---------------------------------------------------------------------------


def test_memory_store_init_enables_wal(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()

    with sqlite3.connect(tmp_path / "memory.db") as conn:
        result = conn.execute("PRAGMA journal_mode;").fetchone()
    assert result[0].lower() == "wal"


def test_memory_store_connection_uses_timeout(tmp_path: Path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()

    captured: list[dict] = []
    original_connect = sqlite3.connect

    def mock_connect(path, **kwargs):
        captured.append(kwargs)
        return original_connect(path, **kwargs)

    with patch("memisalluneed.store.sqlite3.connect", side_effect=mock_connect):
        MemoryStore(tmp_path / "memory.db").list()

    assert any(kwargs.get("timeout") == 30 for kwargs in captured)


# ---------------------------------------------------------------------------
# Task 5: Short-lived HTTP clients
# ---------------------------------------------------------------------------


def test_self_created_http_client_is_closed_after_model_call(monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "test-key")
    exited: list[bool] = []

    original_exit = httpx.Client.__exit__

    def tracking_exit(self, *args):
        exited.append(True)
        return original_exit(self, *args)

    def fake_post(self, *args, **kwargs):
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "reply"}}]},
            request=httpx.Request("POST", "https://example.test/v1/chat/completions"),
        )

    with patch.object(httpx.Client, "post", fake_post), \
         patch.object(httpx.Client, "__exit__", tracking_exit):
        model = OpenAICompatibleChatModel(
            provider=ProviderConfig(
                api_key_env="TEST_API_KEY",
                base_url="https://example.test/v1",
            ),
            model="test-model",
            timeout=5,
        )
        model.complete([{"role": "user", "content": "hi"}])

    assert exited, "httpx.Client was not used as a context manager (not closed) after model call"


# ---------------------------------------------------------------------------
# Task 6: Flush and worker idempotency
# ---------------------------------------------------------------------------


def test_manual_flush_skips_turns_with_pending_running_or_written_jobs(
    tmp_path: Path, monkeypatch
):
    from memisalluneed.config import (
        AppConfig,
        HttpConfig,
        ModelRoleConfig,
        ProviderConfig,
        SessionConfig,
    )
    from memisalluneed.ui_server import UIState, flush_session, job_store_path_for_state

    config_path = tmp_path / "config.toml"
    config_path.write_text("placeholder", encoding="utf-8")
    state = UIState(db_path=tmp_path / "memory.db", config_path=config_path)

    store = MemoryStore(state.db_path)
    store.init()

    session_path = tmp_path / ".memisalluneed" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({
            "session_id": "session-1",
            "created_at": "2026-05-09T00:00:00+00:00",
            "updated_at": "2026-05-09T00:00:00+00:00",
            "turns": [
                {
                    "id": "turn-pending",
                    "user_message": "pending turn",
                    "assistant_message": "reply",
                    "recalled_memory_ids": [],
                    "created_at": "2026-05-09T00:00:00+00:00",
                },
                {
                    "id": "turn-running",
                    "user_message": "running turn",
                    "assistant_message": "reply",
                    "recalled_memory_ids": [],
                    "created_at": "2026-05-09T00:00:01+00:00",
                },
                {
                    "id": "turn-written",
                    "user_message": "written turn",
                    "assistant_message": "reply",
                    "recalled_memory_ids": [],
                    "created_at": "2026-05-09T00:00:02+00:00",
                },
            ],
        }),
        encoding="utf-8",
    )

    job_store = FormationJobStore(job_store_path_for_state(state))
    for turn_id, status in [
        ("turn-pending", "pending"),
        ("turn-running", "running"),
        ("turn-written", "written"),
    ]:
        turn = SessionTurn(
            id=turn_id,
            user_message="x",
            assistant_message="y",
            recalled_memory_ids=[],
            created_at="2026-05-09T00:00:00+00:00",
        )
        job = FormationJob.new(session_id="session-1", turn=turn)
        job_store.append(job)
        if status == "running":
            job_store.mark_running(job.id)
        elif status == "written":
            job_store.mark_running(job.id)
            job_store.mark_written(job.id, [])

    formation_called: list[str] = []

    class TrackingFormationModel:
        def complete(self, messages):
            formation_called.append("called")
            return '{"memories":[]}'

    config = AppConfig(
        chat_model=ModelRoleConfig(provider="openai", model="chat"),
        formation_model=ModelRoleConfig(provider="openai", model="formation"),
        session=SessionConfig(
            max_turns=6,
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
    monkeypatch.setattr("memisalluneed.ui_server.load_config", lambda path: config)
    monkeypatch.setattr(
        "memisalluneed.ui_server.model_from_config",
        lambda config, role: TrackingFormationModel(),
    )

    response = flush_session(state)

    assert response["written_memories"] == []
    assert formation_called == [], f"Formation model was called unexpectedly: {formation_called}"


def test_worker_skips_formation_when_turn_already_has_formed_memory(tmp_path: Path):
    job_store = make_job_store(tmp_path)
    memory_store = MemoryStore(tmp_path / "memory.db")
    memory_store.init()

    turn = make_turn("turn-already-formed")
    already_formed = create_memory_item(
        "already formed memory",
        memory_type="experience",
        metadata={
            "source": "chat_session",
            "formation_kind": "chat_qa",
            "turn_id": "turn-already-formed",
        },
    )
    memory_store.add(already_formed)

    job = FormationJob.new(session_id="s", turn=turn)
    job_store.append(job)

    formation_called: list[str] = []

    class TrackingModel:
        def complete(self, messages):
            formation_called.append("called")
            return '{"memories":[]}'

    worker = FormationWorker(
        job_store=job_store,
        memory_store=memory_store,
        formation_model_factory=lambda: TrackingModel(),
    )
    worker.process_one(job)

    assert formation_called == [], "Worker called formation model for already-formed turn"
    updated = job_store.get(job.id)
    assert updated.status == "written"


# ---------------------------------------------------------------------------
# Task 7: UI error mapping
# ---------------------------------------------------------------------------


def test_ui_error_mapping_returns_distinct_statuses():
    import json as json_module
    import sqlite3 as sqlite3_module

    from memisalluneed.ui_server import error_response_for_exception

    cases: list[tuple[Exception, int]] = [
        (json_module.JSONDecodeError("bad json", "", 0), 400),
        (ValueError("bad value"), 400),
        (KeyError("not found"), 404),
        (RuntimeError("Missing API key environment variable: SOME_KEY"), 503),
        (httpx.TimeoutException("timed out"), 504),
        (
            httpx.HTTPStatusError(
                "upstream error",
                request=httpx.Request("POST", "https://example.test"),
                response=httpx.Response(502),
            ),
            502,
        ),
        (sqlite3_module.Error("db error"), 500),
        (Exception("unknown"), 500),
    ]

    for exc, expected_status in cases:
        status, error_type, message = error_response_for_exception(exc)
        assert status == expected_status, (
            f"For {type(exc).__name__} expected HTTP {expected_status}, got {status}"
        )


# ---------------------------------------------------------------------------
# Task 8: Lightweight integration test
# ---------------------------------------------------------------------------


def test_lightweight_integration_chat_roll_to_worker_to_memory(
    tmp_path: Path, monkeypatch
):
    """
    UI chat rolls an old turn -> pending job created -> worker processes it
    with fake model -> job becomes written -> memory appears in memory.db.
    """
    from memisalluneed.config import (
        AppConfig,
        HttpConfig,
        ModelRoleConfig,
        ProviderConfig,
        SessionConfig,
    )
    from memisalluneed.ui_server import (
        UIState,
        chat_send,
        job_store_for_state,
    )

    config_path = tmp_path / "config.toml"
    config_path.write_text("placeholder", encoding="utf-8")
    state = UIState(db_path=tmp_path / "memory.db", config_path=config_path)
    memory_store = MemoryStore(state.db_path)
    memory_store.init()

    session_path = tmp_path / ".memisalluneed" / "session.json"
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.write_text(
        json.dumps({
            "session_id": "session-1",
            "created_at": "2026-05-09T00:00:00+00:00",
            "updated_at": "2026-05-09T00:00:00+00:00",
            "turns": [
                {
                    "id": "old-turn",
                    "user_message": "old user message",
                    "assistant_message": "old assistant reply",
                    "recalled_memory_ids": [],
                    "created_at": "2026-05-09T00:00:00+00:00",
                }
            ],
        }),
        encoding="utf-8",
    )

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

    class FakeReplyModel:
        def complete(self, messages):
            return "assistant reply"

    formation_json = json.dumps({
        "memories": [{
            "type": "experience",
            "content": "integration test memory",
            "state": "success",
            "confidence": 0.9,
            "metadata": {
                "source": "chat_session",
                "formation_kind": "chat_qa",
                "session_id": "session-1",
                "turn_id": "old-turn",
                "recalled_memory_ids": [],
                "used_memory_ids": [],
            },
        }]
    })

    class FakeFormationModel:
        def complete(self, messages):
            return formation_json

    monkeypatch.setattr("memisalluneed.ui_server.load_config", lambda path: config)
    monkeypatch.setattr(
        "memisalluneed.ui_server.model_from_config",
        lambda config, role: FakeReplyModel() if role.model == "chat" else FakeFormationModel(),
    )

    # Step 1: chat_send rolls the old turn and creates a pending job
    response = chat_send(state, "new message")
    assert response["assistant_reply"] == "assistant reply"
    assert len(response["formation_jobs"]) == 1
    job_id = response["formation_jobs"][0]["id"]
    assert response["formation_jobs"][0]["status"] == "pending"
    assert response["formation_jobs"][0]["turn_id"] == "old-turn"

    # Step 2: verify pending job is in the job store
    job_store = job_store_for_state(state)
    job = job_store.get(job_id)
    assert job.status == "pending"

    # Step 3: worker processes the job
    worker = FormationWorker(
        job_store=job_store,
        memory_store=memory_store,
        formation_model_factory=lambda: FakeFormationModel(),
    )
    worker.process_one(job)

    # Step 4: job is written
    updated_job = job_store.get(job_id)
    assert updated_job.status == "written"
    assert len(updated_job.written_memory_ids) == 1

    # Step 5: memory is in the database
    memories = memory_store.all()
    assert len(memories) == 1
    assert memories[0].content == "integration test memory"
    assert memories[0].metadata.get("turn_id") == "old-turn"
