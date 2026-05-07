from __future__ import annotations

import json
from typing import Any

from memisalluneed.formation import FORMATION_SYSTEM_PROMPT
from memisalluneed.formation import parse_memory_candidates
from memisalluneed.models.base import ChatMessage, ChatModel
from memisalluneed.schema import MemoryItem
from memisalluneed.store import MemoryStore

HOST_INTEGRATION_SYSTEM_PROMPT = (
    FORMATION_SYSTEM_PROMPT
    + "\nYou are integrating host-supplied material. "
    + "Do not add external facts not present in the host input. "
    + "Do not judge sufficiency. Preserve provenance metadata."
)


def build_source_reference_payload(
    *,
    source_uri: str,
    source_title: str | None = None,
    retrieved_at: str | None = None,
    host_agent: str | None = None,
    metadata: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "formation_kind": "host_source_reference",
        "source_uri": source_uri,
        "source_title": source_title,
        "retrieved_at": retrieved_at,
        "host_agent": host_agent,
        "metadata": dict(metadata or {}),
    }


def build_host_evidence_payload(
    *,
    evidence: str,
    query: str | None = None,
    source_ids: list[str] | None = None,
    host_agent: str | None = None,
    confidence: float = 1.0,
    state: str = "success",
    metadata: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "formation_kind": "host_evidence",
        "evidence": evidence,
        "query": query,
        "source_ids": list(source_ids or []),
        "host_agent": host_agent,
        "confidence": confidence,
        "state": state,
        "metadata": dict(metadata or {}),
    }


def build_answer_trace_payload(
    *,
    query: str,
    answer: str,
    evidence_ids: list[str] | None = None,
    source_ids: list[str] | None = None,
    recalled_memory_ids: list[str] | None = None,
    host_agent: str | None = None,
    confidence: float = 1.0,
    state: str = "success",
    metadata: dict[str, object] | None = None,
) -> dict[str, Any]:
    return {
        "formation_kind": "host_answer_trace",
        "query": query,
        "answer": answer,
        "evidence_ids": list(evidence_ids or []),
        "source_ids": list(source_ids or []),
        "recalled_memory_ids": list(recalled_memory_ids or []),
        "host_agent": host_agent,
        "confidence": confidence,
        "state": state,
        "metadata": dict(metadata or {}),
    }


def build_host_integration_messages(payload: dict[str, Any]) -> list[ChatMessage]:
    return [
        {"role": "system", "content": HOST_INTEGRATION_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False, sort_keys=True),
        },
    ]


def _merge_required_metadata(
    memory: MemoryItem,
    required_metadata: dict[str, object],
    extra_metadata: dict[str, object],
) -> MemoryItem:
    metadata = dict(memory.metadata)
    metadata.update(extra_metadata)
    metadata.update(required_metadata)
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


def form_host_supplied_memories(
    *,
    store: MemoryStore,
    formation_model: ChatModel,
    payload: dict[str, Any],
    allowed_types: set[str],
    required_metadata: dict[str, object],
) -> list[MemoryItem]:
    raw_response = formation_model.complete(build_host_integration_messages(payload))
    candidates = parse_memory_candidates(raw_response)
    extra_metadata = payload.get("metadata", {})
    if not isinstance(extra_metadata, dict):
        extra_metadata = {}

    memories: list[MemoryItem] = []
    for candidate in candidates:
        if candidate.type not in allowed_types:
            continue
        memory = _merge_required_metadata(
            candidate,
            required_metadata=required_metadata,
            extra_metadata=extra_metadata,
        )
        store.add(memory)
        memories.append(memory)
    return memories
