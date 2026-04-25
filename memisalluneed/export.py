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
    path.write_text(export_jsonl_text(store), encoding="utf-8")


def export_jsonl_text(store: MemoryStore) -> str:
    lines = [memory_to_jsonl(item) for item in store.all()]
    if not lines:
        return ""
    return "\n".join(lines) + "\n"
