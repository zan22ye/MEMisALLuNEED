from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from memisalluneed.models.base import ChatMessage, ChatModel
from memisalluneed.schema import MemoryItem, create_memory_item
from memisalluneed.session import SessionTurn
from memisalluneed.store import MemoryStore

FORMATION_SYSTEM_PROMPT = """You are the memory formation model for MEMisALLuNEED.
Return only a JSON object with a memories array.
Create cleaned and compressed memories, not raw transcript copies.
Allowed memory types for chat_qa: knowledge, experience, recall.
Allowed memory states: success, failed, uncertain, contradicted, outdated.
Every memory must include confidence as a number from 0.0 to 1.0.
Every memory metadata object must include source="chat_session", formation_kind="chat_qa", session_id, turn_id, recalled_memory_ids, and used_memory_ids.
For each chat_qa turn, emit at least one experience memory.
Every chat_qa experience memory metadata object must include source="chat_session", formation_kind="chat_qa", session_id, turn_id, recalled_memory_ids, and used_memory_ids.
If you emit a recall memory for the same turn, include the same trace metadata.
Do not emit source memories in Phase 3.
Do not include retrieval scores or recall_scores.
Do not talk to the user."""


def _contains_surrogate(value: Any) -> bool:
    if isinstance(value, str):
        return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if isinstance(value, dict):
        return any(
            _contains_surrogate(key) or _contains_surrogate(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_surrogate(item) for item in value)
    return False


def _extract_json_object(raw_json: str) -> str:
    text = raw_json.strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        return fenced.group(1).strip()
    return text


def _content_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = [
            item
            for key in ("zh", "en")
            if isinstance((item := value.get(key)), str) and item.strip()
        ]
        if parts:
            return "\n".join(parts)
    return str(value)


def parse_memory_candidates(raw_json: str) -> list[MemoryItem]:
    try:
        data = json.loads(_extract_json_object(raw_json))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, dict):
        return []

    raw_memories = data.get("memories")
    if not isinstance(raw_memories, list):
        return []

    memories: list[MemoryItem] = []
    for raw_memory in raw_memories:
        if not isinstance(raw_memory, dict):
            continue
        try:
            metadata = raw_memory.get("metadata")
            if metadata is None:
                metadata = {}
            elif not isinstance(metadata, dict):
                continue
            content = _content_to_text(raw_memory.get("content", ""))
            if _contains_surrogate(content) or _contains_surrogate(metadata):
                continue
            confidence = raw_memory.get("confidence", raw_memory.get("importance", 0.7))
            memories.append(
                create_memory_item(
                    content,
                    memory_type=str(raw_memory.get("type", "")),
                    state=str(raw_memory.get("state", "")),
                    confidence=float(confidence),
                    metadata=metadata,
                )
            )
        except (TypeError, ValueError):
            continue

    return memories


def build_chat_qa_payload(
    *,
    session_id: str,
    turn: SessionTurn,
    recalled_memories: list[MemoryItem],
) -> dict[str, Any]:
    return {
        "formation_kind": "chat_qa",
        "session_id": session_id,
        "turn": {
            "id": turn.id,
            "user_message": turn.user_message,
            "assistant_message": turn.assistant_message,
            "created_at": turn.created_at,
        },
        "recalled_memories": [
            {
                "id": memory.id,
                "type": memory.type,
                "state": memory.state,
                "confidence": memory.confidence,
                "content": memory.content,
            }
            for memory in recalled_memories
        ],
        "used_memory_ids": [memory.id for memory in recalled_memories],
    }


def build_formation_messages(payload: dict[str, Any]) -> list[ChatMessage]:
    return [
        {"role": "system", "content": FORMATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        },
    ]


@dataclass
class FormationService:
    model: ChatModel
    store: MemoryStore

    def form_from_chat_qa_turn(
        self,
        *,
        session_id: str,
        turn: SessionTurn,
        recalled_memories: list[MemoryItem],
    ) -> list[MemoryItem]:
        payload = build_chat_qa_payload(
            session_id=session_id,
            turn=turn,
            recalled_memories=recalled_memories,
        )
        return self._form_and_write(payload)

    def _form_and_write(self, payload: dict[str, Any]) -> list[MemoryItem]:
        raw_response = self.model.complete(build_formation_messages(payload))
        memories = parse_memory_candidates(raw_response)
        if payload.get("formation_kind") == "chat_qa":
            memories = [memory for memory in memories if memory.type != "source"]
            memories = [
                _with_chat_qa_trace_metadata(memory, payload) for memory in memories
            ]
        for memory in memories:
            self.store.add(memory)
        return memories


def _with_chat_qa_trace_metadata(
    memory: MemoryItem,
    payload: dict[str, Any],
) -> MemoryItem:
    turn = payload.get("turn", {})
    metadata = dict(memory.metadata)
    metadata.update(
        {
            "source": "chat_session",
            "formation_kind": "chat_qa",
            "session_id": payload.get("session_id"),
            "turn_id": turn.get("id") if isinstance(turn, dict) else None,
            "recalled_memory_ids": [
                memory["id"]
                for memory in payload.get("recalled_memories", [])
                if isinstance(memory, dict) and "id" in memory
            ],
            "used_memory_ids": list(payload.get("used_memory_ids", [])),
        }
    )
    return MemoryItem(
        id=memory.id,
        type=memory.type,
        content=memory.content,
        state=memory.state,
        confidence=memory.confidence,
        metadata=metadata,
        created_at=memory.created_at,
        updated_at=memory.updated_at,
        usage_count=memory.usage_count,
        last_recalled_at=memory.last_recalled_at,
    )
