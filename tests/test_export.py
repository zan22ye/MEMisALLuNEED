import json

from memisalluneed.export import export_jsonl, export_jsonl_text, memory_to_jsonl
from memisalluneed.schema import create_memory_item
from memisalluneed.store import MemoryStore


def test_memory_to_jsonl_outputs_one_json_line():
    item = create_memory_item("Memory can be exported.")

    line = memory_to_jsonl(item)

    parsed = json.loads(line)
    assert parsed["id"] == item.id
    assert parsed["content"] == "Memory can be exported."


def test_memory_to_jsonl_preserves_unicode():
    item = create_memory_item("记忆可以导出。")

    line = memory_to_jsonl(item)

    assert "记忆可以导出。" in line


def test_export_jsonl_writes_all_items(tmp_path):
    db_path = tmp_path / "memory.db"
    output_path = tmp_path / "nested" / "memories.jsonl"
    store = MemoryStore(db_path)
    store.init()
    store.add(create_memory_item("First memory."))
    store.add(create_memory_item("Second memory."))

    export_jsonl(store, output_path)

    lines = output_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(json.loads(line)["id"] for line in lines)


def test_export_jsonl_text_returns_stdout_text(tmp_path):
    store = MemoryStore(tmp_path / "memory.db")
    store.init()
    store.add(create_memory_item("Export to stdout."))

    text = export_jsonl_text(store)

    assert text.endswith("\n")
    lines = text.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["content"] == "Export to stdout."
