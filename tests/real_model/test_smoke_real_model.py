from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from memisalluneed.config import load_config


DATASET_DIR = Path("datasets") / "smoke_real_model"
DATASET_FILES = [
    DATASET_DIR / "recall_qa.jsonl",
    DATASET_DIR / "session_formation.jsonl",
    DATASET_DIR / "timestamp_resolution.jsonl",
    DATASET_DIR / "trace_export.jsonl",
]


def load_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in DATASET_FILES:
        with path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                case = json.loads(stripped)
                case["_dataset_path"] = str(path)
                case["_line_number"] = line_number
                cases.append(case)
    return cases


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "case" in metafunc.fixturenames:
        cases = load_cases()
        ids = [str(case["id"]) for case in cases]
        metafunc.parametrize("case", cases, ids=ids)


def resolve_config_path() -> Path | None:
    configured = os.environ.get("MEMISALLUNEED_TEST_CONFIG")
    if configured:
        path = Path(configured)
        return path if path.exists() else None
    default = Path(".memisalluneed") / "config.toml"
    return default if default.exists() else None


def skip_unless_real_model_enabled() -> Path:
    if os.environ.get("RUN_REAL_MODEL_TESTS") != "1":
        pytest.skip("Set RUN_REAL_MODEL_TESTS=1 to run real-model smoke tests")

    config_path = resolve_config_path()
    if config_path is None:
        pytest.skip(
            "Real-model smoke tests require MEMISALLUNEED_TEST_CONFIG or "
            ".memisalluneed/config.toml"
        )

    config = load_config(config_path)
    required_envs = {
        config.providers[config.chat_model.provider].api_key_env,
        config.providers[config.formation_model.provider].api_key_env,
    }
    missing = sorted(name for name in required_envs if not os.environ.get(name))
    if missing:
        pytest.skip(
            "Real-model smoke tests require API key env vars: "
            + ", ".join(missing)
        )

    return config_path


def test_dataset_contains_eight_cases() -> None:
    assert len(load_cases()) == 8


@pytest.mark.real_model
def test_real_model_smoke_case_is_gated(case: dict[str, Any]) -> None:
    skip_unless_real_model_enabled()
