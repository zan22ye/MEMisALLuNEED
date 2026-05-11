from collections import Counter
from dataclasses import replace

from memisalluneed.schema import create_memory_item
from memisalluneed.search import (
    MemorySearchResult,
    score_memories_bm25,
    search_memories,
    tokenize_terms,
)
from memisalluneed.store import MemoryStore


def test_tokenize_terms_preserves_technical_tokens():
    tokens = tokenize_terms(
        "Use GLM-4.7 with OPENAI_API_KEY, config.example.toml, and memory.db."
    )

    assert "glm-4.7" in tokens
    assert "openai_api_key" in tokens
    assert "config.example.toml" in tokens
    assert "memory.db" in tokens


def test_tokenize_terms_splits_compound_technical_tokens():
    tokens = tokenize_terms("chat_model formation-worker zai-org")

    assert "chat_model" in tokens
    assert "chat" in tokens
    assert "model" in tokens
    assert "formation-worker" in tokens
    assert "formation" in tokens
    assert "worker" in tokens
    assert "zai-org" in tokens
    assert "zai" in tokens
    assert "org" in tokens


def test_tokenize_terms_adds_chinese_two_and_three_grams():
    tokens = tokenize_terms("用户喜欢喝冰美式")

    assert "冰美" in tokens
    assert "美式" in tokens
    assert "冰美式" in tokens


def test_tokenize_terms_does_not_add_chinese_single_character_supplements():
    tokens = tokenize_terms("冰美式")

    assert "冰" not in tokens
    assert "美" not in tokens
    assert "式" not in tokens


def test_tokenize_terms_filters_small_stopword_list():
    tokens = tokenize_terms("我 是 the memory recall")

    assert "我" not in tokens
    assert "是" not in tokens
    assert "the" not in tokens
    assert "memory" in tokens
    assert "recall" in tokens


def test_tokenize_terms_caps_excessive_repetition():
    tokens = tokenize_terms("memory " * 20)
    counts = Counter(tokens)

    assert counts["memory"] == 8


def test_score_memories_bm25_returns_positive_scores_for_english_memory():
    item = create_memory_item("External knowledge is acquired when memory is insufficient.")

    results = score_memories_bm25(
        "when should external knowledge be used",
        [item],
    )

    assert len(results) == 1
    assert results[0].item.id == item.id
    assert results[0].score > 0


def test_score_memories_bm25_returns_positive_scores_for_chinese_memory():
    item = create_memory_item("用户喜欢喝冰美式。")

    results = score_memories_bm25("他喜欢喝什么", [item])

    assert len(results) == 1
    assert results[0].item.id == item.id
    assert results[0].score > 0


def test_score_memories_bm25_gives_rare_terms_more_impact():
    common_only = create_memory_item("memory memory memory recall")
    rare_match = create_memory_item("memory recall kanban")

    results = score_memories_bm25(
        "memory kanban",
        [common_only, rare_match],
    )

    assert results[0].item.id == rare_match.id
    assert results[0].score > results[1].score


def test_score_memories_bm25_applies_length_normalization():
    concise = create_memory_item("memory recall bm25")
    long_weak = create_memory_item(
        "memory recall "
        + " ".join(f"filler{i}" for i in range(80))
    )

    results = score_memories_bm25(
        "memory recall bm25",
        [long_weak, concise],
    )

    assert results[0].item.id == concise.id


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
