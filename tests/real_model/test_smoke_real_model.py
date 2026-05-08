from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from memisalluneed.config import load_config
from memisalluneed.schema import MemoryItem
from memisalluneed.store import MemoryStore


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


def memory_from_fixture(raw: dict[str, Any]) -> MemoryItem:
    created_at = str(raw["created_at"])
    return MemoryItem.from_dict(
        {
            "id": str(raw.get("id") or uuid4()),
            "type": raw["type"],
            "content": raw["content"],
            "state": raw["state"],
            "confidence": raw["confidence"],
            "metadata": dict(raw.get("metadata") or {}),
            "created_at": created_at,
            "updated_at": str(raw.get("updated_at") or created_at),
            "usage_count": int(raw.get("usage_count", 0)),
            "last_recalled_at": raw.get("last_recalled_at"),
        }
    )


def setup_case_store(case: dict[str, Any], db_path: Path) -> list[MemoryItem]:
    store = MemoryStore(db_path)
    store.init()
    setup_items = [memory_from_fixture(raw) for raw in case["setup_memories"]]
    for item in setup_items:
        store.add(item)
    return setup_items


def write_artifact(path: Path, name: str, content: str) -> None:
    artifacts = path / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / name).write_text(content, encoding="utf-8")


def write_json_artifact(path: Path, name: str, value: Any) -> None:
    write_artifact(
        path,
        name,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
    )


def test_dataset_contains_eight_cases() -> None:
    assert len(load_cases()) == 8


def test_memory_from_fixture_preserves_created_at() -> None:
    item = memory_from_fixture(
        {
            "type": "knowledge",
            "content": "Fixture content.",
            "state": "success",
            "confidence": 1.0,
            "created_at": "2026-05-01T10:00:00Z",
            "metadata": {"fixture": True},
        }
    )

    assert item.content == "Fixture content."
    assert item.created_at == "2026-05-01T10:00:00Z"
    assert item.updated_at == "2026-05-01T10:00:00Z"
    assert dict(item.metadata) == {"fixture": True}


def test_setup_case_store_inserts_setup_memories(tmp_path: Path) -> None:
    case = {
        "setup_memories": [
            {
                "type": "knowledge",
                "content": "Alice prefers concise technical answers.",
                "state": "success",
                "confidence": 1.0,
                "created_at": "2026-05-01T10:00:00Z",
                "metadata": {"fixture": True},
            }
        ]
    }

    setup_items = setup_case_store(case, tmp_path / "memory.db")

    assert len(setup_items) == 1
    stored = MemoryStore(tmp_path / "memory.db").all()
    assert [item.content for item in stored] == [
        "Alice prefers concise technical answers."
    ]


@pytest.mark.real_model
def test_real_model_smoke_case(case: dict[str, Any]) -> None:
    skip_unless_real_model_enabled()
