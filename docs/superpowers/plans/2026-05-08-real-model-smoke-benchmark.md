# Real-Model Smoke Benchmark Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a pytest-runnable real-model smoke integration suite for MEMisALLuNEED.

**Architecture:** Add versioned JSONL smoke datasets under `datasets/smoke_real_model/` and a skipped-by-default pytest suite under `tests/real_model/`. The runner loads cases, creates an isolated SQLite database per case, drives `mem chat` through a subprocess with the configured real models, exports memories, writes artifacts, and applies tolerant functional assertions.

**Tech Stack:** Python 3.11, pytest, subprocess, pathlib, json, MEMisALLuNEED CLI, `MemoryStore`, `MemoryItem`, existing TOML config loader.

---

## File Structure

- Create: `datasets/smoke_real_model/recall_qa.jsonl`
  - Two recall QA smoke cases.
- Create: `datasets/smoke_real_model/session_formation.jsonl`
  - Two real formation smoke cases.
- Create: `datasets/smoke_real_model/timestamp_resolution.jsonl`
  - Two timestamp-aware resolution smoke cases.
- Create: `datasets/smoke_real_model/trace_export.jsonl`
  - Two trace and export smoke cases.
- Create: `tests/real_model/test_smoke_real_model.py`
  - Loads datasets, gates execution on env/config/API keys, runs `mem chat`, writes artifacts, and performs assertions.
- Modify: `pyproject.toml`
  - Register the `real_model` pytest marker so `pytest` does not warn on the marker.
- Optional modify after implementation: `docs/roadmap.md`
  - Only add a short note if the project tracks benchmark availability in the roadmap. Skip this if it would mix unrelated roadmap work into this small benchmark task.

---

## Task 1: Add The Dataset Files

**Files:**
- Create: `datasets/smoke_real_model/recall_qa.jsonl`
- Create: `datasets/smoke_real_model/session_formation.jsonl`
- Create: `datasets/smoke_real_model/timestamp_resolution.jsonl`
- Create: `datasets/smoke_real_model/trace_export.jsonl`

- [ ] **Step 1: Create the dataset directory**

Run:

```bash
mkdir -p datasets/smoke_real_model
```

Expected: command exits with code 0.

- [ ] **Step 2: Write `recall_qa.jsonl`**

Create `datasets/smoke_real_model/recall_qa.jsonl` with exactly these two JSONL lines:

```jsonl
{"id":"recall_qa_001","category":"recall_qa","description":"Answer from an existing user preference memory.","setup_memories":[{"type":"knowledge","content":"Alice prefers concise technical answers.","state":"success","confidence":1.0,"created_at":"2026-05-01T10:00:00Z","metadata":{"fixture":true}}],"chat_messages":["How should responses to Alice be styled?"],"expected":{"answer_should_contain_any":["concise","technical"],"trace_should_include_memory":true,"min_total_memories":1}}
{"id":"recall_qa_002","category":"recall_qa","description":"Answer from an existing project storage memory.","setup_memories":[{"type":"knowledge","content":"MEMisALLuNEED uses SQLite as primary storage and JSONL as export format.","state":"success","confidence":1.0,"created_at":"2026-05-01T11:00:00Z","metadata":{"fixture":true}}],"chat_messages":["What storage and export formats does MEMisALLuNEED use?"],"expected":{"answer_should_contain_all":["SQLite","JSONL"],"trace_should_include_memory":true,"min_total_memories":1}}
```

- [ ] **Step 3: Write `session_formation.jsonl`**

Create `datasets/smoke_real_model/session_formation.jsonl` with exactly these two JSONL lines:

```jsonl
{"id":"session_formation_001","category":"session_formation","description":"A simple user preference should be formed into memory after chat exits.","setup_memories":[],"chat_messages":["Remember that my default language is Chinese.","What is my default language?"],"expected":{"answer_should_contain_any":["Chinese","中文"],"min_new_memories":1,"memory_types_should_include":["experience"],"metadata_should_include":{"formation_kind":"chat_qa"}}}
{"id":"session_formation_002","category":"session_formation","description":"A simple project fact should be captured during chat formation.","setup_memories":[],"chat_messages":["Remember that my project codename is Lantern.","What is my project codename?"],"expected":{"answer_should_contain_any":["Lantern"],"min_new_memories":1,"memory_types_should_include":["experience"],"metadata_should_include":{"formation_kind":"chat_qa"}}}
```

- [ ] **Step 4: Write `timestamp_resolution.jsonl`**

Create `datasets/smoke_real_model/timestamp_resolution.jsonl` with exactly these two JSONL lines:

```jsonl
{"id":"timestamp_resolution_001","category":"timestamp_resolution","description":"Prefer the newer editor preference memory.","setup_memories":[{"type":"knowledge","content":"Alice's preferred editor is Vim.","state":"success","confidence":1.0,"created_at":"2026-05-01T10:00:00Z","metadata":{"fixture":true}},{"type":"knowledge","content":"Alice's preferred editor is VS Code.","state":"success","confidence":1.0,"created_at":"2026-05-03T10:00:00Z","metadata":{"fixture":true}}],"chat_messages":["What is Alice's preferred editor now?"],"expected":{"answer_should_contain_any":["VS Code","Visual Studio Code"],"trace_should_include_memory":true,"min_total_memories":2,"old_memory_should_remain":true}}
{"id":"timestamp_resolution_002","category":"timestamp_resolution","description":"Prefer the newer default language memory.","setup_memories":[{"type":"knowledge","content":"Ben's default response language is English.","state":"success","confidence":1.0,"created_at":"2026-05-01T10:00:00Z","metadata":{"fixture":true}},{"type":"knowledge","content":"Ben's default response language is Chinese.","state":"success","confidence":1.0,"created_at":"2026-05-04T10:00:00Z","metadata":{"fixture":true}}],"chat_messages":["What is Ben's default response language now?"],"expected":{"answer_should_contain_any":["Chinese","中文"],"trace_should_include_memory":true,"min_total_memories":2,"old_memory_should_remain":true}}
```

- [ ] **Step 5: Write `trace_export.jsonl`**

Create `datasets/smoke_real_model/trace_export.jsonl` with exactly these two JSONL lines:

```jsonl
{"id":"trace_export_001","category":"trace_export","description":"Trace should show used memory and export should parse.","setup_memories":[{"type":"knowledge","content":"The smoke benchmark should use tolerant assertions.","state":"success","confidence":1.0,"created_at":"2026-05-02T10:00:00Z","metadata":{"fixture":true}}],"chat_messages":["What kind of assertions should the smoke benchmark use?"],"expected":{"answer_should_contain_any":["tolerant","宽松"],"trace_should_include_memory":true,"export_should_parse":true,"min_total_memories":1}}
{"id":"trace_export_002","category":"trace_export","description":"A chat with no setup memory should still export valid JSONL after formation.","setup_memories":[],"chat_messages":["Remember that short smoke tests are easier to debug."],"expected":{"min_new_memories":1,"memory_types_should_include":["experience"],"metadata_should_include":{"formation_kind":"chat_qa"},"export_should_parse":true}}
```

- [ ] **Step 6: Validate the JSONL files parse**

Run:

```bash
python -c 'import json, pathlib; [json.loads(line) for path in pathlib.Path("datasets/smoke_real_model").glob("*.jsonl") for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]'
```

Expected: command exits with code 0.

- [ ] **Step 7: Commit the dataset files**

Run:

```bash
git add datasets/smoke_real_model/recall_qa.jsonl datasets/smoke_real_model/session_formation.jsonl datasets/smoke_real_model/timestamp_resolution.jsonl datasets/smoke_real_model/trace_export.jsonl
git commit -m "Add real-model smoke benchmark datasets"
```

Expected: commit succeeds and includes only the four dataset files.

---

## Task 2: Register The Pytest Marker

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Write the failing marker check**

Run:

```bash
pytest --markers | rg "real_model"
```

Expected before implementation: command exits non-zero because the marker is not registered.

- [ ] **Step 2: Add the marker to `pyproject.toml`**

Modify `[tool.pytest.ini_options]` to include `markers` while preserving the existing `testpaths` and `pythonpath` values:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
markers = [
  "real_model: tests that call configured real chat and formation models",
]
```

- [ ] **Step 3: Verify marker registration**

Run:

```bash
pytest --markers | rg "real_model"
```

Expected: output contains:

```text
@pytest.mark.real_model: tests that call configured real chat and formation models
```

- [ ] **Step 4: Commit the marker registration**

Run:

```bash
git add pyproject.toml
git commit -m "Register real-model pytest marker"
```

Expected: commit succeeds and includes only `pyproject.toml`.

---

## Task 3: Add Dataset Loading And Skip Gating Tests

**Files:**
- Create: `tests/real_model/test_smoke_real_model.py`

- [ ] **Step 1: Create the initial test module with loading and config helpers**

Create `tests/real_model/test_smoke_real_model.py` with this initial content:

```python
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
```

- [ ] **Step 2: Run the dataset loading test**

Run:

```bash
pytest tests/real_model/test_smoke_real_model.py::test_dataset_contains_eight_cases -q
```

Expected: one test passes.

- [ ] **Step 3: Run the gated real-model test without env**

Run:

```bash
pytest tests/real_model/test_smoke_real_model.py::test_real_model_smoke_case_is_gated -q
```

Expected: eight tests skip.

- [ ] **Step 4: Commit the initial test module**

Run:

```bash
git add tests/real_model/test_smoke_real_model.py
git commit -m "Add real-model smoke test gating"
```

Expected: commit succeeds and includes only `tests/real_model/test_smoke_real_model.py`.

---

## Task 4: Add Fixture Insertion And Artifact Helpers

**Files:**
- Modify: `tests/real_model/test_smoke_real_model.py`

- [ ] **Step 1: Replace the gated placeholder test with helper functions and helper tests**

Modify `tests/real_model/test_smoke_real_model.py` so it contains these additional imports:

```python
from uuid import uuid4

from memisalluneed.schema import MemoryItem
from memisalluneed.store import MemoryStore
```

Add these helper functions below `skip_unless_real_model_enabled`:

```python
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
```

Replace `test_real_model_smoke_case_is_gated` with these tests:

```python
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
```

- [ ] **Step 2: Run the helper tests**

Run:

```bash
pytest tests/real_model/test_smoke_real_model.py::test_memory_from_fixture_preserves_created_at tests/real_model/test_smoke_real_model.py::test_setup_case_store_inserts_setup_memories -q
```

Expected: two tests pass.

- [ ] **Step 3: Verify real-model cases still skip without env**

Run:

```bash
pytest tests/real_model/test_smoke_real_model.py::test_real_model_smoke_case -q
```

Expected: eight tests skip.

- [ ] **Step 4: Commit the helper functions**

Run:

```bash
git add tests/real_model/test_smoke_real_model.py
git commit -m "Add real-model smoke runner helpers"
```

Expected: commit succeeds and includes only `tests/real_model/test_smoke_real_model.py`.

---

## Task 5: Add Subprocess Chat, Export, And Artifact Capture

**Files:**
- Modify: `tests/real_model/test_smoke_real_model.py`

- [ ] **Step 1: Add subprocess imports and command helpers**

Add these imports:

```python
import subprocess
import sys
```

Add these helpers below the artifact helpers:

```python
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
```

- [ ] **Step 2: Replace the real-model placeholder with a command smoke body**

Replace `test_real_model_smoke_case` with:

```python
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
```

- [ ] **Step 3: Verify the skipped path still works without env**

Run:

```bash
pytest tests/real_model/test_smoke_real_model.py::test_real_model_smoke_case -q
```

Expected: eight tests skip.

- [ ] **Step 4: Run non-real helper tests**

Run:

```bash
pytest tests/real_model/test_smoke_real_model.py::test_dataset_contains_eight_cases tests/real_model/test_smoke_real_model.py::test_memory_from_fixture_preserves_created_at tests/real_model/test_smoke_real_model.py::test_setup_case_store_inserts_setup_memories -q
```

Expected: three tests pass.

- [ ] **Step 5: Commit subprocess runner work**

Run:

```bash
git add tests/real_model/test_smoke_real_model.py
git commit -m "Run real-model smoke cases through CLI"
```

Expected: commit succeeds and includes only `tests/real_model/test_smoke_real_model.py`.

---

## Task 6: Add Tolerant Assertions

**Files:**
- Modify: `tests/real_model/test_smoke_real_model.py`

- [ ] **Step 1: Add assertion helper functions**

Add these helpers above `test_real_model_smoke_case`:

```python
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
```

- [ ] **Step 2: Call assertion helpers from the real-model test**

Append these lines to the end of `test_real_model_smoke_case`:

```python
    expected = case["expected"]
    assert_answer_contains(chat_result.stdout, expected)
    assert_trace(chat_result.stdout, expected)
    assert_memory_expectations(
        case=case,
        setup_items=setup_items,
        final_memories=final_memories,
    )
    assert_export(export_result.stdout, expected)
```

- [ ] **Step 3: Add focused helper tests**

Add these tests below the existing helper tests:

```python
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
```

- [ ] **Step 4: Run the helper tests**

Run:

```bash
pytest tests/real_model/test_smoke_real_model.py::test_contains_keyword_matches_english_case_insensitively tests/real_model/test_smoke_real_model.py::test_contains_keyword_matches_chinese_by_substring tests/real_model/test_smoke_real_model.py::test_parse_exported_jsonl_requires_objects tests/real_model/test_smoke_real_model.py::test_metadata_contains_requires_exact_key_values -q
```

Expected: four tests pass.

- [ ] **Step 5: Verify skipped real-model tests still skip without env**

Run:

```bash
pytest tests/real_model/test_smoke_real_model.py::test_real_model_smoke_case -q
```

Expected: eight tests skip.

- [ ] **Step 6: Commit assertion helpers**

Run:

```bash
git add tests/real_model/test_smoke_real_model.py
git commit -m "Assert real-model smoke benchmark expectations"
```

Expected: commit succeeds and includes only `tests/real_model/test_smoke_real_model.py`.

---

## Task 7: Verify The Full Non-Real Test Path

**Files:**
- No file changes expected.

- [ ] **Step 1: Run normal tests**

Run:

```bash
pytest -q
```

Expected: existing normal tests pass, and real-model cases are skipped unless `RUN_REAL_MODEL_TESTS=1` is set.

- [ ] **Step 2: Run only real-model tests without enabling env**

Run:

```bash
pytest tests/real_model -q
```

Expected: helper tests pass and the eight real-model case tests skip.

- [ ] **Step 3: Run marker selection without enabling env**

Run:

```bash
pytest -m real_model -q
```

Expected: eight real-model case tests skip.

- [ ] **Step 4: Inspect tracked changes**

Run:

```bash
git status --short
```

Expected: no uncommitted changes from the benchmark implementation tasks except unrelated pre-existing worktree changes that were present before this plan began.

---

## Task 8: Optional Manual Real-Model Verification

**Files:**
- No required file changes.

- [ ] **Step 1: Confirm config and API key env**

Run:

```bash
test -f "${MEMISALLUNEED_TEST_CONFIG:-.memisalluneed/config.toml}"
```

Expected: exits with code 0 when a real-model config exists.

- [ ] **Step 2: Run the real-model smoke suite explicitly**

Run:

```bash
RUN_REAL_MODEL_TESTS=1 pytest tests/real_model -q
```

Expected: the eight case tests run against the configured real chat and formation models. Passing means the real-model smoke benchmark works end to end for the current local configuration.

- [ ] **Step 3: Inspect artifacts on failure**

When a case fails, inspect the pytest temporary path shown in the failure output. The expected files are:

```text
artifacts/case.json
artifacts/stdout.txt
artifacts/stderr.txt
artifacts/export.jsonl
artifacts/memories.json
artifacts/command.txt
artifacts/config_path.txt
```

Use these artifacts to classify the failure as CLI failure, model failure, recall miss, formation miss, metadata issue, or assertion mismatch.

---

## Self-Review Checklist

- Spec coverage:
  - Dataset layout is implemented by Task 1.
  - Eight required cases are implemented by Task 1.
  - Skipped-by-default execution is implemented by Task 3.
  - Config path and API key checks are implemented by Task 3.
  - Isolated DB per case is implemented by Tasks 4 and 5.
  - Normal chat exit and flush formation are implemented by Task 5 through `/exit`.
  - Artifact writing is implemented by Tasks 4 and 5.
  - Tolerant answer, trace, memory, and export assertions are implemented by Task 6.
  - Non-real verification and optional real-model verification are covered by Tasks 7 and 8.
- Placeholder scan:
  - The plan intentionally contains no unresolved placeholder items.
  - Optional future host integration is excluded from implementation tasks.
- Type consistency:
  - Case data uses `dict[str, Any]`.
  - Fixture insertion uses `MemoryItem.from_dict()` to preserve fixed timestamps.
  - Store inspection uses `MemoryStore(db_path).all()`.
  - CLI execution uses `sys.executable -m memisalluneed.cli` so editable install is not required for tests.
