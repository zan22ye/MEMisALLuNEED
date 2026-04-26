from pathlib import Path

import pytest

from memisalluneed.config import ConfigOverrides
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


def test_cli_overrides_replace_config_values(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[chat_model]
provider = "openai"
model = "gpt-4.1"

[formation_model]
provider = "openai"
model = "gpt-4.1-mini"

[session]
max_turns = 6
max_tokens = 100000
recall_top_k = 5

[http]
request_timeout = 60

[providers.openai]
api_key_env = "OPENAI_API_KEY"
base_url = "https://api.openai.com/v1"

[providers.qwen]
api_key_env = "QWEN_API_KEY"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(
        config_path,
        overrides=ConfigOverrides(
            chat_provider="openai",
            chat_model="gpt-4.1-mini",
            formation_provider="qwen",
            formation_model="qwen-turbo",
            max_turns=4,
            max_tokens=1200,
            recall_top_k=3,
        ),
    )

    assert config.chat_model.model == "gpt-4.1-mini"
    assert config.formation_model.provider == "qwen"
    assert config.formation_model.model == "qwen-turbo"
    assert config.session.max_turns == 4
    assert config.session.max_tokens == 1200
    assert config.session.recall_top_k == 3


def test_missing_provider_config_is_rejected(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[chat_model]
provider = "missing"
model = "model"

[formation_model]
provider = "missing"
model = "model"

[session]
max_turns = 6
max_tokens = 100000
recall_top_k = 5

[http]
request_timeout = 60
""".strip(),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Provider config not found: missing"):
        load_config(config_path)
