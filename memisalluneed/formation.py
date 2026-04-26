from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from memisalluneed.models.base import ChatMessage, ChatModel
from memisalluneed.schema import MemoryItem, create_memory_item
from memisalluneed.session import SessionTurn
from memisalluneed.store import MemoryStore

FORMATION_SYSTEM_PROMPT = """You are the memory formation model for MEMisALLuNEED.
Return only a JSON object with a memories array.
Create cleaned and compressed memories, not raw transcript copies.
Allowed memory types: knowledge, experience, recall, source.
Allowed memory states: success, failed, uncertain, contradicted, outdated.
Each memory metadata object must include source="chat_session" and formation_kind.
For rolling formation, include metadata.turn_id.
Do not talk to the user."""


def parse_memory_candidates(raw_json: str) -> list[MemoryItem]:
    try:
        data = json.loads(raw_json)
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
            if not isinstance(metadata, dict):
                continue
            memories.append(
                create_memory_item(
                    str(raw_memory.get("content", "")),
                    memory_type=str(raw_memory.get("type", "")),
                    state=str(raw_memory.get("state", "")),
                    confidence=float(raw_memory.get("confidence")),
                    metadata=metadata,
                )
            )
        except (TypeError, ValueError):
            continue

    return memories


def build_rolling_payload(
    turn: SessionTurn,
    recalled_memories: list[MemoryItem],
) -> dict[str, Any]:
    return {
        "formation_kind": "rolling",
        "turn": turn.to_dict(),
        "recalled_memories": [
            {
                "id": memory.id,
                "type": memory.type,
                "content": memory.content,
            }
            for memory in recalled_memories
        ],
    }


def build_exit_flush_payload(turns: list[SessionTurn]) -> dict[str, Any]:
    return {
        "formation_kind": "exit_flush",
        "turns": [turn.to_dict() for turn in turns],
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

    def form_from_rolled_turn(
        self,
        turn: SessionTurn,
        recalled_memories: list[MemoryItem],
    ) -> list[MemoryItem]:
        payload = build_rolling_payload(turn, recalled_memories)
        return self._form_and_write(payload)

    def form_from_exit_flush(self, turns: list[SessionTurn]) -> list[MemoryItem]:
        payload = build_exit_flush_payload(turns)
        return self._form_and_write(payload)

    def _form_and_write(self, payload: dict[str, Any]) -> list[MemoryItem]:
        raw_response = self.model.complete(build_formation_messages(payload))
        memories = parse_memory_candidates(raw_response)
        for memory in memories:
            self.store.add(memory)
        return memories
