from pathlib import Path

from memisalluneed.config import load_config


def test_load_example_config():
    config = load_config(Path("config.example.toml"))

    assert config.chat_model.provider == "openai"
    assert config.chat_model.model == "gpt-4.1"
    assert config.formation_model.provider == "openai"
    assert config.formation_model.model == "gpt-4.1-mini"
    assert config.session.max_turns == 6
    assert config.session.max_tokens == 100000
    assert config.session.recall_top_k == 5
    assert config.http.request_timeout == 60
    assert config.providers["kimi"].base_url == "https://api.moonshot.cn/v1"
    assert config.providers["qwen"].api_key_env == "QWEN_API_KEY"
