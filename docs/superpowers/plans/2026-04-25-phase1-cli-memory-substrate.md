# Phase 1 CLI Memory Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建第一个可运行的 `mem` CLI，使 memory item 可以被写入、持久化、召回、查看和导出。

**Architecture:** SQLite 是 canonical structured memory store，JSONL 是导出格式。Phase 1 只实现 keyword/token overlap search，不实现 embedding column、不接 vector DB、不接 LLM。

**Tech Stack:** Python 3.11+、标准库 `sqlite3`、`argparse`、`json`、`dataclasses`、`pytest`。

---

## 文件结构

创建以下文件：

- `pyproject.toml`：项目元数据、CLI entry point、pytest 配置。
- `.gitignore`：忽略 `.memisalluneed/`、缓存和构建产物。
- `memisalluneed/__init__.py`：包版本。
- `memisalluneed/schema.py`：`MemoryItem`、type/state 校验、序列化。
- `memisalluneed/store.py`：SQLite 初始化、CRUD、recall metadata 更新。
- `memisalluneed/search.py`：文本归一化、分词、overlap score、排序。
- `memisalluneed/export.py`：JSONL 行序列化与导出。
- `memisalluneed/cli.py`：`mem` CLI。
- `tests/test_store.py`：存储层测试。
- `tests/test_search.py`：搜索层测试。
- `tests/test_export.py`：导出测试。
- `tests/test_cli.py`：CLI smoke tests。
- `examples/memories.jsonl`：版本化示例数据。

---

### Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `memisalluneed/__init__.py`

- [ ] **Step 1: Create project metadata**

Write `pyproject.toml`:

```toml
[project]
name = "memisalluneed"
version = "0.1.0"
description = "A Memory-Centric Agent CLI memory substrate."
readme = "README.md"
requires-python = ">=3.11"
dependencies = []

[project.scripts]
mem = "memisalluneed.cli:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Ignore local runtime data**

Write `.gitignore`:

```gitignore
.memisalluneed/
.pytest_cache/
__pycache__/
*.pyc
*.pyo
*.egg-info/
build/
dist/
```

- [ ] **Step 3: Create package version**

Write `memisalluneed/__init__.py`:

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Commit scaffold**

Run:

```bash
git add pyproject.toml .gitignore memisalluneed/__init__.py
git commit -m "Add Phase 1 project scaffold"
```

Expected: commit succeeds and `.memisalluneed/` remains ignored.

---

### Task 2: Memory Schema

**Files:**
- Create: `memisalluneed/schema.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write schema tests**

Write the first part of `tests/test_store.py`:

```python
import json

import pytest

from memisalluneed.schema import MemoryItem, create_memory_item


def test_create_memory_item_defaults():
    item = create_memory_item("Everything before now is memory.")

    assert item.type == "knowledge"
    assert item.state == "success"
    assert item.confidence == 1.0
    assert item.content == "Everything before now is memory."
    assert item.metadata == {}
    assert item.usage_count == 0
    assert item.last_recalled_at is None
    assert item.id
    assert item.created_at
    assert item.updated_at


def test_memory_item_round_trip_dict():
    item = create_memory_item(
        "External knowledge is acquired when memory is insufficient.",
        memory_type="knowledge",
        state="success",
        confidence=0.9,
        metadata={"source": "spec"},
    )

    restored = MemoryItem.from_dict(item.to_dict())

    assert restored == item
    assert json.loads(json.dumps(restored.to_dict()))["metadata"] == {"source": "spec"}


def test_invalid_memory_type_is_rejected():
    with pytest.raises(ValueError, match="Invalid memory type"):
        create_memory_item("content", memory_type="invalid")


def test_invalid_memory_state_is_rejected():
    with pytest.raises(ValueError, match="Invalid memory state"):
        create_memory_item("content", state="invalid")
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
pytest tests/test_store.py -v
```

Expected: fail because `memisalluneed.schema` does not exist.

- [ ] **Step 3: Implement schema**

Write `memisalluneed/schema.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

MEMORY_TYPES = {"knowledge", "experience", "recall", "source"}
MEMORY_STATES = {"success", "failed", "uncertain", "contradicted", "outdated"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_memory_type(memory_type: str) -> None:
    if memory_type not in MEMORY_TYPES:
        allowed = ", ".join(sorted(MEMORY_TYPES))
        raise ValueError(f"Invalid memory type: {memory_type}. Allowed: {allowed}")


def validate_memory_state(state: str) -> None:
    if state not in MEMORY_STATES:
        allowed = ", ".join(sorted(MEMORY_STATES))
        raise ValueError(f"Invalid memory state: {state}. Allowed: {allowed}")


@dataclass(frozen=True)
class MemoryItem:
    id: str
    type: str
    content: str
    state: str
    confidence: float
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    usage_count: int = 0
    last_recalled_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "state": self.state,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "last_recalled_at": self.last_recalled_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MemoryItem":
        validate_memory_type(data["type"])
        validate_memory_state(data["state"])
        return cls(
            id=data["id"],
            type=data["type"],
            content=data["content"],
            state=data["state"],
            confidence=float(data["confidence"]),
            metadata=dict(data.get("metadata") or {}),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            usage_count=int(data.get("usage_count", 0)),
            last_recalled_at=data.get("last_recalled_at"),
        )


def create_memory_item(
    content: str,
    *,
    memory_type: str = "knowledge",
    state: str = "success",
    confidence: float = 1.0,
    metadata: dict[str, Any] | None = None,
) -> MemoryItem:
    if not content.strip():
        raise ValueError("Memory content cannot be empty")
    validate_memory_type(memory_type)
    validate_memory_state(state)
    if confidence < 0.0 or confidence > 1.0:
        raise ValueError("Confidence must be between 0.0 and 1.0")
    now = utc_now()
    return MemoryItem(
        id=str(uuid4()),
        type=memory_type,
        content=content,
        state=state,
        confidence=confidence,
        metadata=metadata or {},
        created_at=now,
        updated_at=now,
    )
```

- [ ] **Step 4: Run schema tests**

Run:

```bash
pytest tests/test_store.py -v
```

Expected: schema tests pass.

- [ ] **Step 5: Commit schema**

Run:

```bash
git add memisalluneed/schema.py tests/test_store.py
git commit -m "Add memory item schema"
```

---

### Task 3: SQLite Store

**Files:**
- Create: `memisalluneed/store.py`
- Modify: `tests/test_store.py`

- [ ] **Step 1: Add store tests**

Append to `tests/test_store.py`:

```python
from memisalluneed.store import MemoryStore


def test_store_initializes_database(tmp_path):
    db_path = tmp_path / "memory.db"

    store = MemoryStore(db_path)
    store.init()

    assert db_path.exists()


def test_store_add_list_and_get(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    store.init()
    item = create_memory_item("Memory is the core substrate.")

    store.add(item)
    items = store.list(limit=10)
    fetched = store.get(item.id)

    assert [stored.id for stored in items] == [item.id]
    assert fetched == item


def test_store_returns_none_for_missing_item(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    store.init()

    assert store.get("missing") is None


def test_store_updates_recall_metadata(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    store.init()
    item = create_memory_item("Recall should update metadata.")
    store.add(item)

    store.mark_recalled([item.id])
    recalled = store.get(item.id)

    assert recalled is not None
    assert recalled.usage_count == 1
    assert recalled.last_recalled_at is not None
```

- [ ] **Step 2: Run store tests and verify failure**

Run:

```bash
pytest tests/test_store.py -v
```

Expected: fail because `MemoryStore` is not implemented.

- [ ] **Step 3: Implement store**

Write `memisalluneed/store.py`:

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterable

from memisalluneed.schema import MemoryItem, utc_now

DEFAULT_DB_PATH = Path(".memisalluneed") / "memory.db"


class MemoryStore:
    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH) -> None:
        self.db_path = Path(db_path)

    def init(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS memories (
                  id TEXT PRIMARY KEY,
                  type TEXT NOT NULL,
                  content TEXT NOT NULL,
                  state TEXT NOT NULL,
                  confidence REAL NOT NULL,
                  metadata TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  usage_count INTEGER NOT NULL DEFAULT 0,
                  last_recalled_at TEXT
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_state ON memories(state)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_memories_created_at ON memories(created_at)"
            )

    def add(self, item: MemoryItem) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                  id, type, content, state, confidence, metadata,
                  created_at, updated_at, usage_count, last_recalled_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.type,
                    item.content,
                    item.state,
                    item.confidence,
                    json.dumps(item.metadata, ensure_ascii=False, sort_keys=True),
                    item.created_at,
                    item.updated_at,
                    item.usage_count,
                    item.last_recalled_at,
                ),
            )

    def list(self, *, limit: int = 20) -> list[MemoryItem]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memories
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def all(self) -> list[MemoryItem]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM memories ORDER BY created_at DESC"
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def get(self, memory_id: str) -> MemoryItem | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_item(row)

    def mark_recalled(self, memory_ids: Iterable[str]) -> None:
        now = utc_now()
        with self._connect() as connection:
            connection.executemany(
                """
                UPDATE memories
                SET usage_count = usage_count + 1,
                    last_recalled_at = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                [(now, now, memory_id) for memory_id in memory_ids],
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _row_to_item(row: sqlite3.Row) -> MemoryItem:
        return MemoryItem.from_dict(
            {
                "id": row["id"],
                "type": row["type"],
                "content": row["content"],
                "state": row["state"],
                "confidence": row["confidence"],
                "metadata": json.loads(row["metadata"]),
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "usage_count": row["usage_count"],
                "last_recalled_at": row["last_recalled_at"],
            }
        )
```

- [ ] **Step 4: Run store tests**

Run:

```bash
pytest tests/test_store.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit store**

Run:

```bash
git add memisalluneed/store.py tests/test_store.py
git commit -m "Add SQLite memory store"
```

---

### Task 4: Keyword Search

**Files:**
- Create: `memisalluneed/search.py`
- Test: `tests/test_search.py`

- [ ] **Step 1: Write search tests**

Write `tests/test_search.py`:

```python
from memisalluneed.schema import create_memory_item
from memisalluneed.search import MemorySearchResult, search_memories, score_memory
from memisalluneed.store import MemoryStore


def test_score_memory_uses_token_overlap():
    item = create_memory_item("External knowledge is acquired when memory is insufficient.")

    score = score_memory("when should external knowledge be used", item)

    assert score > 0


def test_search_returns_relevant_items_first(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    store.init()
    relevant = create_memory_item("External knowledge is acquired when memory is insufficient.")
    unrelated = create_memory_item("A session keeps only the latest k turns.")
    store.add(unrelated)
    store.add(relevant)

    results = search_memories(store, "when should external knowledge be used", top_k=2)

    assert isinstance(results[0], MemorySearchResult)
    assert results[0].item.id == relevant.id
    assert results[0].score > results[1].score


def test_search_updates_recall_metadata(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    store.init()
    item = create_memory_item("Memory recall should update usage metadata.")
    store.add(item)

    search_memories(store, "memory recall metadata", top_k=1)
    recalled = store.get(item.id)

    assert recalled is not None
    assert recalled.usage_count == 1
    assert recalled.last_recalled_at is not None
```

- [ ] **Step 2: Run search tests and verify failure**

Run:

```bash
pytest tests/test_search.py -v
```

Expected: fail because `memisalluneed.search` does not exist.

- [ ] **Step 3: Implement search**

Write `memisalluneed/search.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass

from memisalluneed.schema import MemoryItem
from memisalluneed.store import MemoryStore


@dataclass(frozen=True)
class MemorySearchResult:
    item: MemoryItem
    score: float


def tokenize(text: str) -> set[str]:
    return {token for token in re.split(r"\W+", text.lower()) if token}


def score_memory(query: str, item: MemoryItem) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0
    memory_tokens = tokenize(item.content)
    overlap = query_tokens.intersection(memory_tokens)
    return len(overlap) / len(query_tokens)


def search_memories(
    store: MemoryStore,
    query: str,
    *,
    top_k: int = 5,
) -> list[MemorySearchResult]:
    scored = [
        MemorySearchResult(item=item, score=score_memory(query, item))
        for item in store.all()
    ]
    ranked = sorted(
        scored,
        key=lambda result: (
            result.score,
            result.item.confidence,
            result.item.created_at,
        ),
        reverse=True,
    )
    results = [result for result in ranked if result.score > 0][:top_k]
    store.mark_recalled([result.item.id for result in results])
    return results
```

- [ ] **Step 4: Run search tests**

Run:

```bash
pytest tests/test_search.py -v
```

Expected: all search tests pass.

- [ ] **Step 5: Commit search**

Run:

```bash
git add memisalluneed/search.py tests/test_search.py
git commit -m "Add keyword memory search"
```

---

### Task 5: JSONL Export

**Files:**
- Create: `memisalluneed/export.py`
- Test: `tests/test_export.py`

- [ ] **Step 1: Write export tests**

Write `tests/test_export.py`:

```python
import json

from memisalluneed.export import export_jsonl, memory_to_jsonl
from memisalluneed.schema import create_memory_item
from memisalluneed.store import MemoryStore


def test_memory_to_jsonl_outputs_one_json_line():
    item = create_memory_item("Memory can be exported.")

    line = memory_to_jsonl(item)

    parsed = json.loads(line)
    assert parsed["id"] == item.id
    assert parsed["content"] == "Memory can be exported."


def test_export_jsonl_writes_all_items(tmp_path):
    db_path = tmp_path / "memory.db"
    output_path = tmp_path / "memories.jsonl"
    store = MemoryStore(db_path)
    store.init()
    store.add(create_memory_item("First memory."))
    store.add(create_memory_item("Second memory."))

    export_jsonl(store, output_path)

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["id"] for line in lines)
```

- [ ] **Step 2: Run export tests and verify failure**

Run:

```bash
pytest tests/test_export.py -v
```

Expected: fail because `memisalluneed.export` does not exist.

- [ ] **Step 3: Implement export**

Write `memisalluneed/export.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from memisalluneed.schema import MemoryItem
from memisalluneed.store import MemoryStore


def memory_to_jsonl(item: MemoryItem) -> str:
    return json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True)


def export_jsonl(store: MemoryStore, output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(memory_to_jsonl(item) for item in store.all())
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def export_jsonl_text(store: MemoryStore) -> str:
    content = "\n".join(memory_to_jsonl(item) for item in store.all())
    if content:
        content += "\n"
    return content
```

- [ ] **Step 4: Run export tests**

Run:

```bash
pytest tests/test_export.py -v
```

Expected: all export tests pass.

- [ ] **Step 5: Commit export**

Run:

```bash
git add memisalluneed/export.py tests/test_export.py
git commit -m "Add JSONL memory export"
```

---

### Task 6: CLI Commands

**Files:**
- Create: `memisalluneed/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write CLI tests**

Write `tests/test_cli.py`:

```python
import json

from memisalluneed.cli import main


def test_cli_init_add_list_search_show_and_export(tmp_path, capsys):
    db_path = tmp_path / "memory.db"

    assert main(["init", "--db", str(db_path)]) == 0
    assert main(["add", "Everything before now is memory.", "--db", str(db_path)]) == 0
    assert main(["list", "--db", str(db_path)]) == 0
    list_output = capsys.readouterr().out
    assert "Everything before now is memory." in list_output

    assert main(["search", "what is memory", "--db", str(db_path)]) == 0
    search_output = capsys.readouterr().out
    assert "score=" in search_output
    memory_id = search_output.split()[0]

    assert main(["show", memory_id, "--json", "--db", str(db_path)]) == 0
    show_output = capsys.readouterr().out
    assert json.loads(show_output)["id"] == memory_id

    assert main(["export", "--db", str(db_path)]) == 0
    export_output = capsys.readouterr().out
    assert json.loads(export_output.splitlines()[0])["content"] == "Everything before now is memory."
```

- [ ] **Step 2: Run CLI tests and verify failure**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: fail because `memisalluneed.cli` does not exist.

- [ ] **Step 3: Implement CLI**

Write `memisalluneed/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from memisalluneed.export import export_jsonl, export_jsonl_text
from memisalluneed.schema import create_memory_item
from memisalluneed.search import search_memories
from memisalluneed.store import DEFAULT_DB_PATH, MemoryStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mem")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--db", default=str(DEFAULT_DB_PATH))

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("content")
    add_parser.add_argument("--type", default="knowledge")
    add_parser.add_argument("--state", default="success")
    add_parser.add_argument("--confidence", type=float, default=1.0)
    add_parser.add_argument("--metadata", default="{}")
    add_parser.add_argument("--db", default=str(DEFAULT_DB_PATH))

    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--limit", type=int, default=20)
    list_parser.add_argument("--db", default=str(DEFAULT_DB_PATH))

    show_parser = subparsers.add_parser("show")
    show_parser.add_argument("id")
    show_parser.add_argument("--json", action="store_true")
    show_parser.add_argument("--db", default=str(DEFAULT_DB_PATH))

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("query")
    search_parser.add_argument("--top-k", type=int, default=5)
    search_parser.add_argument("--db", default=str(DEFAULT_DB_PATH))

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--output")
    export_parser.add_argument("--db", default=str(DEFAULT_DB_PATH))

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = MemoryStore(Path(args.db))

    if args.command == "init":
        store.init()
        print(f"Initialized memory database at {store.db_path}")
        return 0

    if args.command == "add":
        store.init()
        metadata = json.loads(args.metadata)
        item = create_memory_item(
            args.content,
            memory_type=args.type,
            state=args.state,
            confidence=args.confidence,
            metadata=metadata,
        )
        store.add(item)
        print(item.id)
        return 0

    if args.command == "list":
        store.init()
        for item in store.list(limit=args.limit):
            preview = item.content if len(item.content) <= 80 else item.content[:77] + "..."
            print(
                f"{item.id} {item.type} {item.state} "
                f"{item.confidence:.2f} {item.created_at} {preview}"
            )
        return 0

    if args.command == "show":
        store.init()
        item = store.get(args.id)
        if item is None:
            print(f"Memory not found: {args.id}", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True))
        else:
            for key, value in item.to_dict().items():
                print(f"{key}: {value}")
        return 0

    if args.command == "search":
        store.init()
        for result in search_memories(store, args.query, top_k=args.top_k):
            preview = result.item.content
            print(f"{result.item.id} score={result.score:.3f} {preview}")
        return 0

    if args.command == "export":
        store.init()
        if args.output:
            export_jsonl(store, args.output)
            print(f"Exported memories to {args.output}")
        else:
            print(export_jsonl_text(store), end="")
        return 0

    parser.error(f"Unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
pytest tests/test_cli.py -v
```

Expected: CLI smoke test passes.

- [ ] **Step 5: Commit CLI**

Run:

```bash
git add memisalluneed/cli.py tests/test_cli.py
git commit -m "Add mem CLI commands"
```

---

### Task 7: Example Data and Docs Sync

**Files:**
- Create: `examples/memories.jsonl`
- Modify: `README.md`
- Modify: `README_zh.md`

- [ ] **Step 1: Add example memories**

Write `examples/memories.jsonl`:

```jsonl
{"content":"Everything before the current moment can be treated as memory.","confidence":1.0,"created_at":"2026-04-25T00:00:00+00:00","id":"example-memory-1","last_recalled_at":null,"metadata":{"source":"project-thesis"},"state":"success","type":"knowledge","updated_at":"2026-04-25T00:00:00+00:00","usage_count":0}
{"content":"External knowledge is acquired only when existing memory is insufficient.","confidence":1.0,"created_at":"2026-04-25T00:00:00+00:00","id":"example-memory-2","last_recalled_at":null,"metadata":{"source":"phase1-spec"},"state":"success","type":"knowledge","updated_at":"2026-04-25T00:00:00+00:00","usage_count":0}
```

- [ ] **Step 2: Add English quickstart**

Append this section to `README.md` before `## Project Status`:

````markdown
## Phase 1 CLI Quickstart

The first runnable milestone is the `mem` CLI.

```bash
mem init
mem add "Everything before the current moment can be treated as memory."
mem add "External knowledge is acquired only when memory is insufficient."
mem list
mem search "when should external knowledge be used"
mem export
```

Runtime data is stored in `.memisalluneed/memory.db`, which is ignored by git.
````

- [ ] **Step 3: Add Chinese quickstart**

Append this section to `README_zh.md` before `## 项目状态`:

````markdown
## Phase 1 CLI 快速开始

第一个可运行里程碑是 `mem` CLI。

```bash
mem init
mem add "Everything before the current moment can be treated as memory."
mem add "External knowledge is acquired only when memory is insufficient."
mem list
mem search "when should external knowledge be used"
mem export
```

本地运行数据存放在 `.memisalluneed/memory.db`，该目录不会提交到 git。
````

- [ ] **Step 4: Commit examples and docs**

Run:

```bash
git add examples/memories.jsonl README.md README_zh.md
git commit -m "Add Phase 1 CLI examples"
```

---

### Task 8: Full Verification

**Files:**
- Verify: all Phase 1 files

- [ ] **Step 1: Run full test suite**

Run:

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Install package in editable mode**

Run:

```bash
python -m pip install -e .
```

Expected: installation succeeds and `mem` command is available.

- [ ] **Step 3: Run acceptance flow**

Run:

```bash
rm -rf .memisalluneed
mem init
mem add "Everything before the current moment can be treated as memory."
mem add "External knowledge is acquired only when memory is insufficient."
mem list
mem search "when should external knowledge be used"
mem export --output examples/memories.jsonl
```

Expected:

- `.memisalluneed/memory.db` exists.
- `mem list` shows two memories.
- `mem search` returns the external knowledge memory.
- `examples/memories.jsonl` contains valid JSONL.

- [ ] **Step 4: Confirm ignored runtime data**

Run:

```bash
git status --short
```

Expected: `.memisalluneed/` does not appear.

- [ ] **Step 5: Final commit**

Run:

```bash
git add .
git commit -m "Complete Phase 1 CLI memory substrate"
```

Expected: commit contains only source, tests, docs, and examples. It must not include `.codex` or `.memisalluneed/`.

---

## Self-Review

- Spec coverage: plan covers CLI entry, SQLite store, JSONL export, keyword search, `.memisalluneed/` ignore rule, example data, tests, and acceptance flow.
- Embedding/vector policy: plan does not add an `embedding` column and does not introduce vector DB in Phase 1.
- Scope control: plan excludes LLM memory formation, session rolling write, external knowledge acquisition, graph reasoning, conflict detection, and benchmark evaluation.
- Type consistency: all modules use `MemoryItem`, `MemoryStore`, `MemorySearchResult`, `search_memories`, `export_jsonl`, and `export_jsonl_text` consistently.
