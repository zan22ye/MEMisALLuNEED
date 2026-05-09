# BM25 Memory Recall Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace token-overlap memory search with BM25 recall and a recall-oriented tokenizer.

**Architecture:** Keep `search_memories(store, query, top_k)` as the public search entry point used by CLI, UI, and chat recall. Implement BM25 and `tokenize_terms(text) -> list[str]` inside `memisalluneed/search.py`, delete the old overlap helpers, and update `tests/test_search.py` to verify tokenizer and BM25 behavior directly.

**Tech Stack:** Python 3.11+, standard library `collections`, `math`, `re`, `unicodedata`, existing `jieba`, pytest.

---

## File Structure

- Modify: `memisalluneed/search.py`
  - Owns `MemorySearchResult`.
  - Exposes `tokenize_terms(text) -> list[str]`.
  - Exposes `score_memories_bm25(query, items) -> list[MemorySearchResult]`.
  - Exposes `search_memories(store, query, top_k=5) -> list[MemorySearchResult]`.
  - Removes `tokenize(text) -> set[str]`.
  - Removes `score_memory(query, item)`.
- Modify: `tests/test_search.py`
  - Removes direct tests for overlap scoring.
  - Adds tokenizer tests for technical tokens, compound splits, Chinese n-grams, stopwords, and repetition caps.
  - Adds BM25 ranking tests for English, Chinese, rare terms, length normalization, empty query, recall metadata, result type, and relevance-first ranking.

---

### Task 1: Replace Search Tests With BM25 Expectations

**Files:**
- Modify: `tests/test_search.py`

- [ ] **Step 1: Replace imports and remove overlap tests**

Replace the top imports in `tests/test_search.py` with:

```python
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
```

Delete these old tests because their target APIs will be removed:

```python
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
```

- [ ] **Step 2: Add tokenizer tests**

Add these tests near the top of `tests/test_search.py`:

```python
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
```

- [ ] **Step 3: Add direct BM25 scorer tests**

Add these tests after the tokenizer tests:

```python
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
```

- [ ] **Step 4: Update existing search tests**

Keep the existing tests for search metadata and relevance-first behavior, but update the relevant-query test name and assertion if needed:

```python
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
```

- [ ] **Step 5: Run search tests and verify expected import failures**

Run:

```bash
uv run pytest tests/test_search.py -q
```

Expected: FAIL because `tokenize_terms` and `score_memories_bm25` are not implemented yet, and old imports were removed.

- [ ] **Step 6: Commit failing tests**

```bash
git add tests/test_search.py
git commit -m "test: define BM25 search behavior"
```

---

### Task 2: Implement Recall-Oriented Tokenization

**Files:**
- Modify: `memisalluneed/search.py`
- Test: `tests/test_search.py`

- [ ] **Step 1: Add tokenizer constants and imports**

In `memisalluneed/search.py`, replace the current imports with:

```python
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import jieba

from memisalluneed.schema import MemoryItem
from memisalluneed.store import MemoryStore
```

Add these constants after `MemorySearchResult`:

```python
BM25_K1 = 1.5
BM25_B = 0.75
MAX_TOKEN_REPETITIONS = 8

STOPWORDS = {
    "的",
    "了",
    "是",
    "我",
    "你",
    "他",
    "她",
    "它",
    "在",
    "和",
    "与",
    "吗",
    "呢",
    "啊",
    "这",
    "那",
    "一个",
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "of",
    "to",
    "in",
    "on",
    "for",
    "and",
    "or",
}

TECHNICAL_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._/-][a-z0-9]+)+|[a-z0-9]+")
CHINESE_SPAN_RE = re.compile(r"[\u4e00-\u9fff]+")
```

- [ ] **Step 2: Add tokenizer helper functions**

Add these functions before `search_memories`:

```python
def tokenize_terms(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    terms: list[str] = []

    for match in TECHNICAL_TOKEN_RE.finditer(normalized):
        token = match.group(0).strip("._/-")
        if token:
            terms.append(token)
            terms.extend(_split_compound_token(token))

    for token in jieba.lcut(normalized):
        token = token.strip()
        if token and not _is_punctuation_only(token):
            terms.append(token)

    for span in CHINESE_SPAN_RE.findall(normalized):
        terms.extend(_chinese_ngrams(span, min_n=2, max_n=3))

    return _filter_and_cap_terms(terms)


def _split_compound_token(token: str) -> list[str]:
    if not any(separator in token for separator in ("_", "-", "/", ".")):
        return []
    return [
        part
        for part in re.split(r"[._/-]+", token)
        if part and part != token
    ]


def _chinese_ngrams(text: str, *, min_n: int, max_n: int) -> list[str]:
    grams: list[str] = []
    for size in range(min_n, max_n + 1):
        if len(text) < size:
            continue
        grams.extend(text[index : index + size] for index in range(len(text) - size + 1))
    return grams


def _filter_and_cap_terms(terms: list[str]) -> list[str]:
    counts: Counter[str] = Counter()
    filtered: list[str] = []
    for term in terms:
        if not term or term in STOPWORDS or _is_punctuation_only(term):
            continue
        if counts[term] >= MAX_TOKEN_REPETITIONS:
            continue
        counts[term] += 1
        filtered.append(term)
    return filtered


def _is_punctuation_only(text: str) -> bool:
    return all(unicodedata.category(char).startswith("P") for char in text)
```

- [ ] **Step 3: Remove old overlap helpers**

Delete these functions from `memisalluneed/search.py`:

```python
def tokenize(text: str) -> set[str]:
    normalized = text.lower()
    tokens = {token for token in re.split(r"\W+", normalized) if token}
    tokens.update(token.strip() for token in jieba.cut(normalized) if token.strip())
    return tokens


def score_memory(query: str, item: MemoryItem) -> float:
    query_tokens = tokenize(query)
    if not query_tokens:
        return 0.0

    memory_tokens = tokenize(item.content)
    return len(query_tokens & memory_tokens) / len(query_tokens)
```

- [ ] **Step 4: Run tokenizer tests**

Run:

```bash
uv run pytest tests/test_search.py::test_tokenize_terms_preserves_technical_tokens tests/test_search.py::test_tokenize_terms_splits_compound_technical_tokens tests/test_search.py::test_tokenize_terms_adds_chinese_two_and_three_grams tests/test_search.py::test_tokenize_terms_does_not_add_chinese_single_character_supplements tests/test_search.py::test_tokenize_terms_filters_small_stopword_list tests/test_search.py::test_tokenize_terms_caps_excessive_repetition -q
```

Expected: PASS for tokenizer tests, FAIL for BM25 tests because the scorer is not implemented yet.

- [ ] **Step 5: Commit tokenizer implementation**

```bash
git add memisalluneed/search.py tests/test_search.py
git commit -m "feat: add BM25 search tokenizer"
```

---

### Task 3: Implement BM25 Batch Scoring

**Files:**
- Modify: `memisalluneed/search.py`
- Test: `tests/test_search.py`

- [ ] **Step 1: Add BM25 scoring functions**

Add these functions after the tokenizer helpers in `memisalluneed/search.py`:

```python
def score_memories_bm25(
    query: str,
    items: list[MemoryItem],
) -> list[MemorySearchResult]:
    query_terms = tokenize_terms(query)
    if not query_terms or not items:
        return []

    document_terms = [tokenize_terms(item.content) for item in items]
    document_lengths = [len(terms) for terms in document_terms]
    non_empty_lengths = [length for length in document_lengths if length > 0]
    if not non_empty_lengths:
        return []

    avg_doc_len = sum(non_empty_lengths) / len(non_empty_lengths)
    document_frequencies = _document_frequencies(document_terms)
    total_documents = len(items)

    results: list[MemorySearchResult] = []
    for item, terms, doc_len in zip(items, document_terms, document_lengths):
        if doc_len == 0:
            continue
        score = _bm25_score(
            query_terms=query_terms,
            document_terms=terms,
            document_frequencies=document_frequencies,
            total_documents=total_documents,
            doc_len=doc_len,
            avg_doc_len=avg_doc_len,
        )
        if score > 0:
            results.append(MemorySearchResult(item=item, score=score))
    return results


def _document_frequencies(document_terms: list[list[str]]) -> Counter[str]:
    frequencies: Counter[str] = Counter()
    for terms in document_terms:
        frequencies.update(set(terms))
    return frequencies


def _bm25_score(
    *,
    query_terms: list[str],
    document_terms: list[str],
    document_frequencies: Counter[str],
    total_documents: int,
    doc_len: int,
    avg_doc_len: float,
) -> float:
    term_frequencies = Counter(document_terms)
    score = 0.0
    for term in query_terms:
        tf = term_frequencies.get(term, 0)
        if tf == 0:
            continue
        df = document_frequencies[term]
        idf = math.log(1 + ((total_documents - df + 0.5) / (df + 0.5)))
        denominator = tf + BM25_K1 * (1 - BM25_B + BM25_B * (doc_len / avg_doc_len))
        score += idf * ((tf * (BM25_K1 + 1)) / denominator)
    return score
```

- [ ] **Step 2: Run direct BM25 tests**

Run:

```bash
uv run pytest tests/test_search.py::test_score_memories_bm25_returns_positive_scores_for_english_memory tests/test_search.py::test_score_memories_bm25_returns_positive_scores_for_chinese_memory tests/test_search.py::test_score_memories_bm25_gives_rare_terms_more_impact tests/test_search.py::test_score_memories_bm25_applies_length_normalization -q
```

Expected: PASS.

- [ ] **Step 3: Commit BM25 scorer**

```bash
git add memisalluneed/search.py tests/test_search.py
git commit -m "feat: score memories with BM25"
```

---

### Task 4: Route Public Search Through BM25

**Files:**
- Modify: `memisalluneed/search.py`
- Test: `tests/test_search.py`

- [ ] **Step 1: Replace `search_memories` implementation**

Replace the existing `search_memories` body with:

```python
def search_memories(
    store: MemoryStore,
    query: str,
    top_k: int = 5,
) -> list[MemorySearchResult]:
    results = score_memories_bm25(query, store.all())
    results.sort(
        key=lambda result: (
            result.score,
            result.item.confidence,
            result.item.created_at,
        ),
        reverse=True,
    )
    results = results[:top_k]
    store.mark_recalled(result.item.id for result in results)
    return results
```

- [ ] **Step 2: Run all search tests**

Run:

```bash
uv run pytest tests/test_search.py -q
```

Expected: PASS.

- [ ] **Step 3: Verify removed APIs are gone**

Run:

```bash
rg "score_memory|def tokenize\\(" memisalluneed tests
```

Expected: no matches.

- [ ] **Step 4: Commit public search routing**

```bash
git add memisalluneed/search.py tests/test_search.py
git commit -m "feat: use BM25 for memory search"
```

---

### Task 5: Run Integration-Focused Regression Checks

**Files:**
- Verify: `memisalluneed/cli.py`
- Verify: `memisalluneed/ui_server.py`
- Verify: `tests/test_chat_cli.py`
- Verify: `tests/test_resolution.py`

- [ ] **Step 1: Run search and dependent unit tests**

Run:

```bash
uv run pytest tests/test_search.py tests/test_resolution.py tests/test_chat_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run CLI search smoke command**

Run:

```bash
tmpdir="$(mktemp -d)" && uv run mem init --db "$tmpdir/memory.db" && uv run mem add "用户喜欢喝冰美式" --db "$tmpdir/memory.db" && uv run mem search "喜欢喝什么" --db "$tmpdir/memory.db"
```

Expected: command exits `0` and prints the memory containing `用户喜欢喝冰美式` with a positive `score=...`.

- [ ] **Step 3: Run full test suite**

Run:

```bash
uv run pytest -q
```

Expected: PASS, except tests explicitly marked or configured to skip because they require real model credentials.

- [ ] **Step 4: Commit any regression fixes**

If Step 1, 2, or 3 required code fixes, commit them:

```bash
git add memisalluneed/search.py tests/test_search.py tests/test_chat_cli.py tests/test_resolution.py
git commit -m "fix: stabilize BM25 recall regressions"
```

If no fixes were required, do not create an empty commit.

---

## Self-Review

- Spec coverage: This plan covers BM25 default search, public `search_memories` stability, removal of overlap helpers, recall-oriented tokenizer, no new dependencies, no persistent index, no embeddings, ranking tie-breakers, recall metadata updates, and focused tests.
- Scope check: The work is a single subsystem change in `memisalluneed/search.py` plus its tests. CLI, UI, and chat remain call-site compatible.
- Type consistency: The plan consistently uses `tokenize_terms(text) -> list[str]`, `score_memories_bm25(query, items) -> list[MemorySearchResult]`, `MemorySearchResult.score`, and `search_memories(store, query, top_k=5)`.
