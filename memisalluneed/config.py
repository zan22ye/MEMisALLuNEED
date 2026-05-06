from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path(".memisalluneed") / "config.toml"


@dataclass(frozen=True)
class ModelRoleConfig:
    provider: str
    model: str


@dataclass(frozen=True)
class SessionConfig:
    max_turns: int
    max_tokens: int
    recall_top_k: int
    recall_candidate_k: int


@dataclass(frozen=True)
class HttpConfig:
    request_timeout: float


@dataclass(frozen=True)
class ProviderConfig:
    api_key_env: str
    base_url: str


@dataclass(frozen=True)
class AppConfig:
    chat_model: ModelRoleConfig
    formation_model: ModelRoleConfig
    session: SessionConfig
    http: HttpConfig
    providers: dict[str, ProviderConfig]


@dataclass(frozen=True)
class ConfigOverrides:
    chat_provider: str | None = None
    chat_model: str | None = None
    formation_provider: str | None = None
    formation_model: str | None = None
    max_turns: int | None = None
    max_tokens: int | None = None
    recall_top_k: int | None = None
    recall_candidate_k: int | None = None


def load_config(
    path: str | Path = DEFAULT_CONFIG_PATH,
    *,
    overrides: ConfigOverrides | None = None,
) -> AppConfig:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    overrides = overrides or ConfigOverrides()

    chat_model = _load_model_role(data, "chat_model")
    formation_model = _load_model_role(data, "formation_model")
    session = _load_session(data)
    http = _load_http(data)
    providers = _load_providers(data)

    chat_model = ModelRoleConfig(
        provider=overrides.chat_provider or chat_model.provider,
        model=overrides.chat_model or chat_model.model,
    )
    formation_model = ModelRoleConfig(
        provider=overrides.formation_provider or formation_model.provider,
        model=overrides.formation_model or formation_model.model,
    )
    session = SessionConfig(
        max_turns=overrides.max_turns
        if overrides.max_turns is not None
        else session.max_turns,
        max_tokens=overrides.max_tokens
        if overrides.max_tokens is not None
        else session.max_tokens,
        recall_top_k=overrides.recall_top_k
        if overrides.recall_top_k is not None
        else session.recall_top_k,
        recall_candidate_k=overrides.recall_candidate_k
        if overrides.recall_candidate_k is not None
        else session.recall_candidate_k,
    )

    _validate_positive_int("session.max_turns", session.max_turns)
    _validate_positive_int("session.max_tokens", session.max_tokens)
    _validate_positive_int("session.recall_top_k", session.recall_top_k)
    _validate_positive_int("session.recall_candidate_k", session.recall_candidate_k)
    if session.recall_candidate_k < session.recall_top_k:
        raise ValueError(
            "session.recall_candidate_k must be greater than or equal to "
            "session.recall_top_k"
        )
    _require_provider(providers, chat_model.provider)
    _require_provider(providers, formation_model.provider)

    return AppConfig(
        chat_model=chat_model,
        formation_model=formation_model,
        session=session,
        http=http,
        providers=providers,
    )


def _load_model_role(data: dict[str, Any], section: str) -> ModelRoleConfig:
    raw = _required_mapping(data, section)
    provider = _required_str(raw, "provider", section)
    model = _required_str(raw, "model", section)
    return ModelRoleConfig(provider=provider, model=model)


def _load_session(data: dict[str, Any]) -> SessionConfig:
    raw = _required_mapping(data, "session")
    max_turns = _required_int(raw, "max_turns", "session")
    max_tokens = _required_int(raw, "max_tokens", "session")
    recall_top_k = _required_int(raw, "recall_top_k", "session")
    recall_candidate_k = _required_int(raw, "recall_candidate_k", "session")
    _validate_positive_int("session.max_turns", max_turns)
    _validate_positive_int("session.max_tokens", max_tokens)
    _validate_positive_int("session.recall_top_k", recall_top_k)
    _validate_positive_int("session.recall_candidate_k", recall_candidate_k)
    if recall_candidate_k < recall_top_k:
        raise ValueError(
            "session.recall_candidate_k must be greater than or equal to "
            "session.recall_top_k"
        )
    return SessionConfig(
        max_turns=max_turns,
        max_tokens=max_tokens,
        recall_top_k=recall_top_k,
        recall_candidate_k=recall_candidate_k,
    )


def _load_http(data: dict[str, Any]) -> HttpConfig:
    raw = _required_mapping(data, "http")
    request_timeout = _required_number(raw, "request_timeout", "http")
    if request_timeout <= 0:
        raise ValueError("http.request_timeout must be positive")
    return HttpConfig(request_timeout=request_timeout)


def _load_providers(data: dict[str, Any]) -> dict[str, ProviderConfig]:
    raw_value = data.get("providers", {})
    if not isinstance(raw_value, dict):
        raise ValueError("Missing required config section: providers")
    raw = raw_value
    providers: dict[str, ProviderConfig] = {}
    for name, value in raw.items():
        if not isinstance(value, dict):
            raise ValueError(f"providers.{name} must be a table")
        providers[name] = ProviderConfig(
            api_key_env=_required_str(value, "api_key_env", f"providers.{name}"),
            base_url=_required_str(value, "base_url", f"providers.{name}"),
        )
    return providers


def _required_mapping(data: dict[str, Any], section: str) -> dict[str, Any]:
    value = data.get(section)
    if not isinstance(value, dict):
        raise ValueError(f"Missing required config section: {section}")
    return value


def _required_str(data: dict[str, Any], key: str, section: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{section}.{key} must be a non-empty string")
    return value


def _required_int(data: dict[str, Any], key: str, section: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f"{section}.{key} must be an integer")
    return value


def _required_number(data: dict[str, Any], key: str, section: str) -> float:
    value = data.get(key)
    if not isinstance(value, int | float):
        raise ValueError(f"{section}.{key} must be a number")
    return float(value)


def _validate_positive_int(name: str, value: int) -> None:
    if value <= 0:
        raise ValueError(f"{name} must be positive")


def _require_provider(
    providers: dict[str, ProviderConfig],
    provider_name: str,
) -> None:
    if provider_name not in providers:
        raise ValueError(f"Provider config not found: {provider_name}")
