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


def test_to_dict_metadata_mutation_does_not_mutate_item():
    item = create_memory_item("content", metadata={"source": "spec"})
    serialized = item.to_dict()

    serialized["metadata"]["source"] = "changed"

    assert item.metadata == {"source": "spec"}


def test_original_metadata_mutation_does_not_mutate_item():
    metadata = {"source": "spec"}
    item = create_memory_item("content", metadata=metadata)

    metadata["source"] = "changed"

    assert item.metadata == {"source": "spec"}


def test_item_metadata_direct_mutation_is_rejected():
    item = create_memory_item("content", metadata={"source": "spec"})

    with pytest.raises(TypeError):
        item.metadata["source"] = "changed"


def test_invalid_memory_type_is_rejected():
    with pytest.raises(ValueError, match="Invalid memory type"):
        create_memory_item("content", memory_type="invalid")


def test_invalid_memory_state_is_rejected():
    with pytest.raises(ValueError, match="Invalid memory state"):
        create_memory_item("content", state="invalid")


def test_empty_memory_content_is_rejected():
    with pytest.raises(ValueError, match="Memory content cannot be empty"):
        create_memory_item("   ")


def test_out_of_range_confidence_is_rejected():
    with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
        create_memory_item("content", confidence=1.1)


def test_nan_confidence_is_rejected():
    with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
        create_memory_item("content", confidence=float("nan"))


def test_from_dict_rejects_empty_content():
    data = create_memory_item("content").to_dict()
    data["content"] = ""

    with pytest.raises(ValueError, match="Memory content cannot be empty"):
        MemoryItem.from_dict(data)


def test_from_dict_rejects_out_of_range_confidence():
    data = create_memory_item("content").to_dict()
    data["confidence"] = -0.1

    with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
        MemoryItem.from_dict(data)


def test_from_dict_rejects_nan_confidence():
    data = create_memory_item("content").to_dict()
    data["confidence"] = float("nan")

    with pytest.raises(ValueError, match="Confidence must be between 0.0 and 1.0"):
        MemoryItem.from_dict(data)
