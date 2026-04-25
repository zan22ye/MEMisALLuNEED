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
    unrelated = create_memory_item("A session should keep only the latest k turns.")
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


def test_search_returns_no_results_for_empty_query(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    store.init()
    store.add(create_memory_item("Memory recall should update usage metadata."))

    results = search_memories(store, "   ", top_k=1)

    assert results == []
