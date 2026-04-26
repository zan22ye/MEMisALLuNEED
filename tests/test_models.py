import httpx
import pytest

from memisalluneed.config import ProviderConfig
from memisalluneed.models.openai_compatible import OpenAICompatibleChatModel


def test_openai_compatible_model_posts_chat_completions(monkeypatch):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["authorization"] = request.headers["Authorization"]
        seen["json"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "assistant reply"}}]},
        )

    monkeypatch.setenv("TEST_API_KEY", "secret")
    client = httpx.Client(transport=httpx.MockTransport(handler))
    model = OpenAICompatibleChatModel(
        provider=ProviderConfig(
            api_key_env="TEST_API_KEY",
            base_url="https://example.test/v1",
        ),
        model="test-model",
        timeout=12,
        client=client,
    )

    reply = model.complete(
        [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "hello"},
        ]
    )

    assert reply == "assistant reply"
    assert seen["url"] == "https://example.test/v1/chat/completions"
    assert seen["authorization"] == "Bearer secret"
    assert '"model":"test-model"' in seen["json"].replace(" ", "")


def test_missing_api_key_is_clear(monkeypatch):
    monkeypatch.delenv("MISSING_API_KEY", raising=False)
    model = OpenAICompatibleChatModel(
        provider=ProviderConfig(
            api_key_env="MISSING_API_KEY",
            base_url="https://example.test/v1",
        ),
        model="test-model",
        timeout=12,
        client=httpx.Client(
            transport=httpx.MockTransport(lambda request: httpx.Response(200))
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Missing API key environment variable: MISSING_API_KEY",
    ):
        model.complete([{"role": "user", "content": "hello"}])
