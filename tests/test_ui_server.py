from __future__ import annotations

import json
from pathlib import Path

from memisalluneed.store import MemoryStore
from memisalluneed.ui_server import UIState, build_status, error_response
from memisalluneed.ui_server import (
    add_memory,
    export_memories,
    get_memory,
    list_memories,
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
