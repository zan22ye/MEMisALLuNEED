from __future__ import annotations

import json
from pathlib import Path

from memisalluneed.config import AppConfig, HttpConfig, ModelRoleConfig, ProviderConfig
from memisalluneed.config import SessionConfig
from memisalluneed.schema import create_memory_item
from memisalluneed.store import MemoryStore
from memisalluneed.ui_server import UIState, build_status, error_response
from memisalluneed.ui_server import (
    add_memory,
    chat_send,
    clear_session,
    export_memories,
    flush_session,
    get_memory,
    list_memories,
    new_session,
    search_memory_results,
)


def test_build_status_reports_paths_without_api_keys(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[chat_model]
provider = "openai"
model = "chat"
[formation_model]
provider = "openai"
model = "formation"
[session]
max_turns = 6
max_tokens = 100000
recall_top_k = 5
recall_candidate_k = 50
[http]
request_timeout = 60
[providers.openai]
api_key_env = "OPENAI_API_KEY"
base_url = "https://example.test/v1"
""".strip(),
        encoding="utf-8",
    )
    state = UIState(db_path=db_path, config_path=config_path)

    status = build_status(state)

    assert status == {
        "db_path": str(db_path),
        "config_path": str(config_path),
        "db_exists": False,
        "config_exists": True,
    }
    assert "OPENAI_API_KEY" not in json.dumps(status)


def test_error_response_has_stable_shape():
    status, headers, body = error_response("bad_request", "Invalid metadata JSON", 400)

    assert status == 400
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert json.loads(body.decode("utf-8")) == {
        "error": {
            "type": "bad_request",
            "message": "Invalid metadata JSON",
        }
    }


def test_memory_helpers_list_add_get_search_and_export(tmp_path: Path):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")

    added = add_memory(
        state,
        {
            "content": "Alice prefers concise technical answers.",
            "type": "knowledge",
            "state": "success",
            "confidence": 0.9,
            "metadata": {"fixture": True},
        },
    )

    assert added["type"] == "knowledge"
    assert added["content"] == "Alice prefers concise technical answers."
    assert list_memories(state, limit=20, memory_type="knowledge", memory_state="success")
    assert get_memory(state, added["id"])["id"] == added["id"]
    results = search_memory_results(state, "concise technical", top_k=5)
    assert results[0]["memory"]["id"] == added["id"]
    assert results[0]["score"] > 0
    assert "Alice prefers concise technical answers." in export_memories(state)
    assert MemoryStore(state.db_path).get(added["id"]) is not None


def test_add_memory_rejects_invalid_metadata(tmp_path: Path):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")

    try:
        add_memory(
            state,
            {
                "content": "Bad metadata.",
                "type": "knowledge",
                "state": "success",
                "confidence": 1.0,
                "metadata": "not-object",
            },
        )
    except ValueError as error:
        assert "metadata must be an object" in str(error)
    else:
        raise AssertionError("expected ValueError")


class FakeReplyModel:
    def complete(self, messages):
        return "assistant reply"


class FakeFormationModel:
    def complete(self, messages):
        return (
            '{"memories":[{"type":"experience","content":"formed chat memory",'
            '"state":"success","confidence":0.8,'
            '"metadata":{"source":"chat_session","formation_kind":"chat_qa",'
            '"session_id":"s","turn_id":"t","recalled_memory_ids":[],'
            '"used_memory_ids":[]}}]}'
        )


def test_chat_send_uses_run_chat_path(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text("placeholder", encoding="utf-8")
    state = UIState(db_path=tmp_path / "memory.db", config_path=config_path)
    store = MemoryStore(state.db_path)
    store.init()
    store.add(create_memory_item("Project uses SQLite storage."))
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
        lambda config, role: FakeReplyModel()
        if role.model == "chat"
        else FakeFormationModel(),
    )

    response = chat_send(state, "How is storage handled?", resume=False)

    assert response["assistant_reply"] == "assistant reply"
    assert response["used_memories"][0]["content"] == "Project uses SQLite storage."


def test_session_controls_use_session_file(tmp_path: Path, monkeypatch):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")
    session_path = tmp_path / ".memisalluneed" / "session.json"
    session_path.parent.mkdir()
    session_path.write_text(
        '{"session_id":"s","created_at":"t","updated_at":"t","turns":[]}',
        encoding="utf-8",
    )

    clear_session(state)

    assert not session_path.exists()
    new_session(state)
    assert not session_path.exists()


def test_flush_session_returns_written_memories(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text("placeholder", encoding="utf-8")
    state = UIState(db_path=tmp_path / "memory.db", config_path=config_path)
    store = MemoryStore(state.db_path)
    store.init()
    session_path = tmp_path / ".memisalluneed" / "session.json"
    session_path.parent.mkdir()
    session_path.write_text(
        """
{
  "session_id": "session-1",
  "created_at": "2026-05-08T00:00:00+00:00",
  "updated_at": "2026-05-08T00:00:00+00:00",
  "turns": [
    {
      "id": "turn-1",
      "user_message": "hello",
      "assistant_message": "reply",
      "recalled_memory_ids": [],
      "created_at": "2026-05-08T00:00:00+00:00"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
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
        lambda config, role: FakeFormationModel(),
    )

    response = flush_session(state)

    assert response["ok"] is True
    assert response["written_memories"][0]["content"] == "formed chat memory"
