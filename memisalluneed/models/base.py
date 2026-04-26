from __future__ import annotations

from typing import Protocol, TypedDict


class ChatMessage(TypedDict):
    role: str
    content: str


class ChatModel(Protocol):
    def complete(self, messages: list[ChatMessage]) -> str:
        raise NotImplementedError
