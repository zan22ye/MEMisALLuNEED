from __future__ import annotations

import json
import os
import subprocess
import sys
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
REQUIRED_EXPORT_FIELDS = {
    "id",
    "type",
    "content",
    "state",
    "confidence",
    "metadata",
    "created_at",
    "updated_at",
}


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


def run_command(
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 120,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )


def run_chat_case(
    *,
    case: dict[str, Any],
    case_dir: Path,
    db_path: Path,
    config_path: Path,
) -> subprocess.CompletedProcess[str]:
    chat_input = "\n".join([*case["chat_messages"], "/exit", ""])
    command = [
        sys.executable,
        "-m",
        "memisalluneed.cli",
        "chat",
        "--db",
        str(db_path),
        "--config",
        str(config_path),
        "--show-memory-trace",
        "--new-session",
        "--no-resume",
    ]
    write_artifact(case_dir, "command.txt", " ".join(command))
    write_artifact(case_dir, "config_path.txt", str(config_path))
    result = run_command(command, input_text=chat_input, timeout=120)
    write_artifact(case_dir, "stdout.txt", result.stdout)
    write_artifact(case_dir, "stderr.txt", result.stderr)
    return result


def run_export_case(
    *,
    case_dir: Path,
    db_path: Path,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "memisalluneed.cli",
        "export",
        "--db",
        str(db_path),
    ]
    result = run_command(command, timeout=30)
    write_artifact(case_dir, "export.jsonl", result.stdout)
    if result.stderr:
        write_artifact(case_dir, "export.stderr.txt", result.stderr)
    return result


def contains_keyword(text: str, keyword: str) -> bool:
    if any("\u4e00" <= char <= "\u9fff" for char in keyword):
        return keyword in text
    return keyword.casefold() in text.casefold()


def assert_answer_contains(stdout: str, expected: dict[str, Any]) -> None:
    any_keywords = expected.get("answer_should_contain_any")
    if any_keywords:
        assert any(
            contains_keyword(stdout, str(keyword)) for keyword in any_keywords
        ), f"stdout did not contain any of {any_keywords!r}\nstdout:\n{stdout}"

    all_keywords = expected.get("answer_should_contain_all")
    if all_keywords:
        missing = [
            str(keyword)
            for keyword in all_keywords
            if not contains_keyword(stdout, str(keyword))
        ]
        assert not missing, f"stdout missed {missing!r}\nstdout:\n{stdout}"


def assert_trace(stdout: str, expected: dict[str, Any]) -> None:
    if not expected.get("trace_should_include_memory"):
        return
    assert "Used memories:" in stdout
    trace_index = stdout.index("Used memories:")
    trace_text = stdout[trace_index:]
    assert "- none" not in trace_text, stdout


def metadata_contains(memory_metadata: dict[str, Any], expected: dict[str, Any]) -> bool:
    return all(memory_metadata.get(key) == value for key, value in expected.items())


def assert_memory_expectations(
    *,
    case: dict[str, Any],
    setup_items: list[MemoryItem],
    final_memories: list[dict[str, Any]],
) -> None:
    expected = case["expected"]
    setup_count = len(setup_items)

    min_total = expected.get("min_total_memories")
    if min_total is not None:
        assert len(final_memories) >= int(min_total)

    min_new = expected.get("min_new_memories")
    if min_new is not None:
        assert len(final_memories) - setup_count >= int(min_new)

    final_types = {str(memory["type"]) for memory in final_memories}
    for memory_type in expected.get("memory_types_should_include", []):
        assert memory_type in final_types

    expected_metadata = expected.get("metadata_should_include")
    if expected_metadata:
        assert any(
            metadata_contains(dict(memory["metadata"]), expected_metadata)
            for memory in final_memories
        ), f"No memory metadata contained {expected_metadata!r}"

    if expected.get("old_memory_should_remain"):
        final_ids = {str(memory["id"]) for memory in final_memories}
        final_contents = {str(memory["content"]) for memory in final_memories}
        for setup_item in setup_items:
            assert (
                setup_item.id in final_ids or setup_item.content in final_contents
            ), f"setup memory disappeared: {setup_item.to_dict()!r}"


def parse_exported_jsonl(raw_jsonl: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in raw_jsonl.splitlines():
        if not line.strip():
            continue
        value = json.loads(line)
        assert isinstance(value, dict)
        rows.append(value)
    return rows


def assert_export(export_stdout: str, expected: dict[str, Any]) -> None:
    if not expected.get("export_should_parse"):
        return
    rows = parse_exported_jsonl(export_stdout)
    for row in rows:
        missing = REQUIRED_EXPORT_FIELDS.difference(row)
        assert not missing, f"exported row missing fields {missing!r}: {row!r}"


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


def test_contains_keyword_matches_english_case_insensitively() -> None:
    assert contains_keyword("Use SQLite and JSONL.", "sqlite")


def test_contains_keyword_matches_chinese_by_substring() -> None:
    assert contains_keyword("默认语言是中文。", "中文")


def test_parse_exported_jsonl_requires_objects() -> None:
    rows = parse_exported_jsonl('{"id":"one","type":"knowledge"}\n')

    assert rows == [{"id": "one", "type": "knowledge"}]


def test_metadata_contains_requires_exact_key_values() -> None:
    assert metadata_contains(
        {"formation_kind": "chat_qa", "source": "chat_session"},
        {"formation_kind": "chat_qa"},
    )
    assert not metadata_contains(
        {"formation_kind": "host_evidence"},
        {"formation_kind": "chat_qa"},
    )


@pytest.mark.real_model
def test_real_model_smoke_case(case: dict[str, Any], tmp_path: Path) -> None:
    config_path = skip_unless_real_model_enabled()
    case_dir = tmp_path / str(case["id"])
    case_dir.mkdir(parents=True)
    db_path = case_dir / "memory.db"

    write_json_artifact(case_dir, "case.json", case)
    setup_items = setup_case_store(case, db_path)
    write_json_artifact(
        case_dir,
        "setup_memories.json",
        [item.to_dict() for item in setup_items],
    )

    chat_result = run_chat_case(
        case=case,
        case_dir=case_dir,
        db_path=db_path,
        config_path=config_path,
    )
    assert chat_result.returncode == 0, (
        f"mem chat failed for {case['id']}\n"
        f"stdout:\n{chat_result.stdout}\n"
        f"stderr:\n{chat_result.stderr}"
    )

    export_result = run_export_case(case_dir=case_dir, db_path=db_path)
    assert export_result.returncode == 0, (
        f"mem export failed for {case['id']}\n"
        f"stdout:\n{export_result.stdout}\n"
        f"stderr:\n{export_result.stderr}"
    )

    final_memories = [item.to_dict() for item in MemoryStore(db_path).all()]
    write_json_artifact(case_dir, "memories.json", final_memories)

    expected = case["expected"]
    assert_answer_contains(chat_result.stdout, expected)
    assert_trace(chat_result.stdout, expected)
    assert_memory_expectations(
        case=case,
        setup_items=setup_items,
        final_memories=final_memories,
    )
    assert_export(export_result.stdout, expected)
