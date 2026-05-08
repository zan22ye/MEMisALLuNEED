from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memisalluneed.config import DEFAULT_CONFIG_PATH
from memisalluneed.export import export_jsonl_text
from memisalluneed.schema import MemoryItem, create_memory_item
from memisalluneed.search import search_memories
from memisalluneed.store import DEFAULT_DB_PATH
from memisalluneed.store import MemoryStore


JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}


@dataclass(frozen=True)
class UIState:
    db_path: Path = DEFAULT_DB_PATH
    config_path: Path = DEFAULT_CONFIG_PATH


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def error_response(
    error_type: str,
    message: str,
    status: int,
) -> tuple[int, dict[str, str], bytes]:
    return (
        status,
        JSON_HEADERS,
        json_bytes({"error": {"type": error_type, "message": message}}),
    )


def build_status(state: UIState) -> dict[str, object]:
    return {
        "db_path": str(state.db_path),
        "config_path": str(state.config_path),
        "db_exists": state.db_path.exists(),
        "config_exists": state.config_path.exists(),
    }


def store_for_state(state: UIState) -> MemoryStore:
    store = MemoryStore(state.db_path)
    store.init()
    return store


def memory_to_response(item: MemoryItem) -> dict[str, Any]:
    return item.to_dict()


def list_memories(
    state: UIState,
    *,
    limit: int,
    memory_type: str | None = None,
    memory_state: str | None = None,
) -> list[dict[str, Any]]:
    memories = store_for_state(state).list(limit=limit)
    if memory_type:
        memories = [memory for memory in memories if memory.type == memory_type]
    if memory_state:
        memories = [memory for memory in memories if memory.state == memory_state]
    return [memory_to_response(memory) for memory in memories]


def get_memory(state: UIState, memory_id: str) -> dict[str, Any] | None:
    item = store_for_state(state).get(memory_id)
    if item is None:
        return None
    return memory_to_response(item)


def add_memory(state: UIState, payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    item = create_memory_item(
        str(payload.get("content", "")),
        memory_type=str(payload.get("type", "knowledge")),
        state=str(payload.get("state", "success")),
        confidence=float(payload.get("confidence", 1.0)),
        metadata=metadata,
    )
    store_for_state(state).add(item)
    return memory_to_response(item)


def search_memory_results(
    state: UIState,
    query: str,
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    return [
        {"score": result.score, "memory": memory_to_response(result.item)}
        for result in search_memories(store_for_state(state), query, top_k=top_k)
    ]


def export_memories(state: UIState) -> str:
    return export_jsonl_text(store_for_state(state))
