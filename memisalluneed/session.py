from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from memisalluneed.file_io import write_json_atomic
from memisalluneed.schema import utc_now

DEFAULT_SESSION_PATH = Path(".memisalluneed") / "session.json"


def approximate_tokens(text: str) -> int:
    """Approximate token count deterministically as one token per four chars."""
    if not text:
        return 0
    return (len(text) + 3) // 4


@dataclass
class SessionTurn:
    id: str
    user_message: str
    assistant_message: str
    recalled_memory_ids: list[str]
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "user_message": self.user_message,
            "assistant_message": self.assistant_message,
            "recalled_memory_ids": list(self.recalled_memory_ids),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SessionTurn":
        return cls(
            id=str(data["id"]),
            user_message=str(data["user_message"]),
            assistant_message=str(data["assistant_message"]),
            recalled_memory_ids=[str(value) for value in data["recalled_memory_ids"]],
            created_at=str(data["created_at"]),
        )

    @property
    def token_count(self) -> int:
        return approximate_tokens(self.user_message) + approximate_tokens(
            self.assistant_message
        )


@dataclass
class SessionState:
    session_id: str
    created_at: str
    updated_at: str
    turns: list[SessionTurn] = field(default_factory=list)

    @classmethod
    def new(cls) -> "SessionState":
        now = utc_now()
        return cls(
            session_id=str(uuid4()),
            created_at=now,
            updated_at=now,
            turns=[],
        )

    @classmethod
    def load(cls, path: str | Path) -> "SessionState":
        session_path = Path(path)
        if not session_path.exists():
            return cls.new()
        data = json.loads(session_path.read_text(encoding="utf-8"))
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> "SessionState":
        raw_turns = data.get("turns", [])
        if not isinstance(raw_turns, list):
            raise ValueError("Session turns must be a list")
        return cls(
            session_id=str(data["session_id"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            turns=[
                SessionTurn.from_dict(turn)
                for turn in raw_turns
                if isinstance(turn, dict)
            ],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "turns": [turn.to_dict() for turn in self.turns],
        }

    def save(self, path: str | Path) -> None:
        self.updated_at = utc_now()
        write_json_atomic(Path(path), self.to_dict())

    def clear_file(self, path: str | Path) -> None:
        session_path = Path(path)
        if session_path.exists():
            session_path.unlink()

    def add_turn(self, turn: SessionTurn) -> None:
        self.turns.append(turn)
        self.updated_at = utc_now()

    def roll_excess(self, *, max_turns: int, max_tokens: int) -> list[SessionTurn]:
        rolled: list[SessionTurn] = []
        while len(self.turns) > max_turns or self.active_tokens > max_tokens:
            rolled.append(self.turns.pop(0))
        if rolled:
            self.updated_at = utc_now()
        return rolled

    @property
    def active_tokens(self) -> int:
        return sum(turn.token_count for turn in self.turns)
