from __future__ import annotations

import os
from typing import Any

import httpx

from memisalluneed.config import ProviderConfig
from memisalluneed.models.base import ChatMessage


class OpenAICompatibleChatModel:
    def __init__(
        self,
        *,
        provider: ProviderConfig,
        model: str,
        timeout: float,
        client: httpx.Client | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.timeout = timeout
        self.client = client or httpx.Client(timeout=timeout)

    def complete(self, messages: list[ChatMessage]) -> str:
        api_key = os.environ.get(self.provider.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Missing API key environment variable: {self.provider.api_key_env}"
            )

        response = self.client.post(
            f"{self.provider.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": self.model,
                "messages": messages,
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        return _parse_assistant_content(response.json())


def _parse_assistant_content(data: dict[str, Any]) -> str:
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError("Malformed model response: missing assistant content") from error

    if not isinstance(content, str):
        raise RuntimeError("Malformed model response: assistant content is not text")
    return content
