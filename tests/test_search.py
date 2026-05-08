from dataclasses import replace

from memisalluneed.schema import create_memory_item
from memisalluneed.search import MemorySearchResult, search_memories, score_memory
from memisalluneed.search import tokenize
from memisalluneed.store import MemoryStore


def test_score_memory_uses_token_overlap():
    item = create_memory_item("External knowledge is acquired when memory is insufficient.")

    score = score_memory("when should external knowledge be used", item)

    assert score > 0


def test_score_memory_handles_chinese_overlap_without_spaces():
    item = create_memory_item("用户喜欢喝冰美式。")

    score = score_memory("他喜欢喝什么", item)

    assert score > 0


def test_tokenize_uses_jieba_for_chinese_words():
    tokens = tokenize("自然语言处理")

    assert "自然语言" in tokens


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


def test_mem_search_ranking_remains_relevance_first(tmp_path):
    db_path = tmp_path / "memory.db"
    store = MemoryStore(db_path)
    store.init()
    newer_low_relevance = create_memory_item("external")
    newer_low_relevance = replace(
        newer_low_relevance,
        created_at="2026-05-01T00:00:00+00:00",
        updated_at="2026-05-01T00:00:00+00:00",
    )
    older_high_relevance = create_memory_item(
        "external knowledge memory insufficient"
    )
    older_high_relevance = replace(
        older_high_relevance,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
    )
    store.add(newer_low_relevance)
    store.add(older_high_relevance)

    results = search_memories(
        store,
        "external knowledge memory insufficient",
        top_k=2,
    )

    assert results[0].item.id == older_high_relevance.id
