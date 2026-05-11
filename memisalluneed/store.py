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
            connection.executescript(
                """
                PRAGMA busy_timeout = 30000;
                PRAGMA journal_mode = WAL;

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
                );

                CREATE INDEX IF NOT EXISTS idx_memories_type
                    ON memories(type);
                CREATE INDEX IF NOT EXISTS idx_memories_state
                    ON memories(state);
                CREATE INDEX IF NOT EXISTS idx_memories_created_at
                    ON memories(created_at);
                CREATE INDEX IF NOT EXISTS idx_memories_last_recalled_at
                    ON memories(last_recalled_at);
                """
            )

    def add(self, item: MemoryItem) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    id,
                    type,
                    content,
                    state,
                    confidence,
                    metadata,
                    created_at,
                    updated_at,
                    usage_count,
                    last_recalled_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.type,
                    item.content,
                    item.state,
                    item.confidence,
                    json.dumps(dict(item.metadata), sort_keys=True),
                    item.created_at,
                    item.updated_at,
                    item.usage_count,
                    item.last_recalled_at,
                ),
            )

    def list(self, limit: int = 20) -> list[MemoryItem]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memories
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_item(row) for row in rows]

    def all(self) -> list[MemoryItem]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memories
                ORDER BY created_at DESC, id DESC
                """
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
        ids = list(memory_ids)
        if not ids:
            return

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
                [(now, now, memory_id) for memory_id in ids],
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path, timeout=30)
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
