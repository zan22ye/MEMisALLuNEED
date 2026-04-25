from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

MEMORY_TYPES = {"knowledge", "experience", "recall", "source"}
MEMORY_STATES = {"success", "failed", "uncertain", "contradicted", "outdated"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_memory_type(memory_type: str) -> None:
    if memory_type not in MEMORY_TYPES:
        allowed = ", ".join(sorted(MEMORY_TYPES))
        raise ValueError(f"Invalid memory type: {memory_type}. Allowed: {allowed}")


def validate_memory_state(state: str) -> None:
    if state not in MEMORY_STATES:
        allowed = ", ".join(sorted(MEMORY_STATES))
        raise ValueError(f"Invalid memory state: {state}. Allowed: {allowed}")


@dataclass(frozen=True)
class MemoryItem:
    id: str
    type: str
    content: str
    state: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    usage_count: int = 0
    last_recalled_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "state": self.state,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "last_recalled_at": self.last_recalled_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryItem":
        validate_memory_type(data["type"])
        validate_memory_state(data["state"])
        return cls(
            id=data["id"],
            type=data["type"],
            content=data["content"],
            state=data["state"],
            confidence=float(data["confidence"]),
            metadata=dict(data.get("metadata") or {}),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            usage_count=int(data.get("usage_count", 0)),
            last_recalled_at=data.get("last_recalled_at"),
        )


def create_memory_item(
    content: str,
    *,
    memory_type: str = "knowledge",
    state: str = "success",
    confidence: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> MemoryItem:
    if not content.strip():
        raise ValueError("Memory content cannot be empty")
    validate_memory_type(memory_type)
    validate_memory_state(state)
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("Confidence must be between 0.0 and 1.0")
    now = utc_now()
    return MemoryItem(
        id=str(uuid4()),
        type=memory_type,
        content=content,
        state=state,
        confidence=confidence,
        metadata=metadata or {},
        created_at=now,
        updated_at=now,
    )
