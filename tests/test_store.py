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
