# BM25 Memory Recall Design

Date: 2026-05-09

## Goal

Replace the current token-overlap memory search ranking with BM25 as the default recall scorer.

The purpose is to make local memory recall more useful without changing how callers use search. BM25 should improve ranking by accounting for term frequency, inverse document frequency, and memory length normalization while keeping the system lightweight and inspectable.

## Current Behavior

Memory search currently lives in `memisalluneed/search.py`.

The current scorer:

- tokenizes English and numeric text with a regular expression;
- tokenizes Chinese text with `jieba`;
- scores each memory independently by query-token overlap;
- ranks by score, then confidence, then creation time.

This is simple but weak for recall because all matched tokens are treated as equally useful. A common term can count as much as a rare term, repeated evidence does not help much, and long memories can match by accident.

## Scope

This change replaces the default search scoring algorithm with BM25.

In scope:

- Use BM25 for `search_memories(store, query, top_k)`.
- Keep `search_memories` as the public search entry point.
- Keep `MemorySearchResult` and its `score` field.
- Replace the overlap-era tokenizer API with a BM25 term-list tokenizer.
- Return only results with positive BM25 scores.
- Continue marking returned memories as recalled.
- Preserve current call sites in CLI, chat recall, and UI search.
- Add focused unit tests for BM25 ranking behavior.

Out of scope:

- Embeddings.
- A SQLite `embedding` column.
- Vector databases or external search services.
- Persistent BM25 indexes.
- SQLite FTS5.
- Configurable search algorithm selection.
- Hybrid semantic ranking.
- LLM reranking.

## Design

BM25 becomes the default implementation behind `search_memories`.

`search_memories` will load memory items from `store.all()`, tokenize the query, tokenize each memory's `content`, compute BM25 corpus statistics for that search, score each memory, sort the positive results, mark returned memories as recalled, and return the top `k` results.

The public behavior remains:

```python
search_memories(store, query, top_k=5) -> list[MemorySearchResult]
```

`MemorySearchResult.score` will represent a BM25 score instead of an overlap ratio.

## BM25 Formula

Use standard BM25 with fixed constants:

```text
k1 = 1.5
b = 0.75
```

For each query term and memory document:

```text
score += idf(term) * ((tf * (k1 + 1)) / (tf + k1 * (1 - b + b * doc_len / avg_doc_len)))
```

Implementation details:

- `tf` is the term frequency in the memory content.
- `doc_len` is the number of tokens in the memory content.
- `avg_doc_len` is the average token length across the current corpus.
- `df` is the number of memory documents containing the term.
- `idf` should use a non-negative BM25-style formula so terms that appear in every memory do not dominate ranking.
- Empty query tokens return no results.
- Empty memory content receives score `0`.

## Tokenization

Tokenization should remain local to `memisalluneed/search.py`, but the old overlap-oriented tokenizer API should be removed.

The implementation should expose only the tokenizer needed by BM25:

```python
tokenize_terms(text: str) -> list[str]
```

This tokenizer returns a token list, not a token set, because BM25 needs term frequency.

The tokenizer should be recall-oriented rather than linguistically perfect. It should improve lexical recall for local memory content that mixes natural language, Chinese, English, commands, config keys, file paths, model names, and API-related identifiers.

The first implementation should:

- lowercase text;
- normalize Unicode text before token extraction;
- extract ASCII words, numbers, and technical fragments with regular expressions;
- preserve useful mixed technical tokens such as `gpt-4.1`, `glm-4.7`, `openai_api_key`, `config.example.toml`, and `memory.db`;
- split compound technical tokens into useful subparts, so `chat_model` can produce `chat_model`, `chat`, and `model`;
- segment Chinese text with `jieba`;
- add supplemental Chinese 2-gram and 3-gram tokens for continuous Chinese spans;
- avoid single-character Chinese supplemental tokens;
- remove punctuation-only tokens and empty tokens;
- filter a small built-in stopword list for very common Chinese and English function words;
- cap excessive repetition of the same token within one text so repeated words cannot dominate BM25 scoring.

The tokenizer should not introduce a new dependency beyond `jieba`.

The supplemental Chinese n-grams are meant to improve recall for short Chinese queries and phrases. They should be limited to 2-grams and 3-grams to avoid the high false-positive rate caused by single-character tokens.

The built-in stopword list should stay intentionally small. It should remove obvious high-frequency function words, not domain terms. Example stopwords include:

```text
Chinese: 的 了 是 我 你 他 她 它 在 和 与 吗 呢 啊 这 那 一个
English: the a an is are was were of to in on for and or
```

The implementation should not keep the old `tokenize(text) -> set[str]` helper. Tests should validate tokenization through the BM25 term-list tokenizer and through `search_memories`.

## Compatibility

The core compatibility requirement is to keep `search_memories` stable, because that is what CLI, UI, and chat recall use.

The overlap-era helpers should be removed:

- remove `score_memory(query, item)`;
- remove `tokenize(text) -> set[str]`.

These functions are not used by in-repo production call sites outside the current search implementation, and keeping them would preserve concepts that no longer match the BM25 design.

Recommended internal shape:

```python
tokenize_terms(text) -> list[str]
score_memories_bm25(query, items) -> list[MemorySearchResult]
```

Then:

```python
search_memories(...)
```

can call the BM25 batch scorer and handle result filtering, sorting, top-k truncation, and recall metadata updates.

## Ranking

Sort results by:

1. BM25 score, descending.
2. `MemoryItem.confidence`, descending.
3. `MemoryItem.created_at`, descending.

This preserves the current rule that relevance is primary, while keeping confidence and recency as tie-breakers.

## Why No Persistent Index

The current project is still a local CLI/UI memory system with modest expected memory counts. Rebuilding BM25 statistics from `store.all()` on each search keeps the implementation small, transparent, and easy to test.

A persistent index can be reconsidered later if memory volume makes search latency visible. That later design should evaluate SQLite FTS5 or a dedicated local index file rather than changing the memory table schema to store embeddings.

## Tests

Add or update tests in `tests/test_search.py`.

Required coverage:

- BM25 returns positive scores for relevant English memory.
- BM25 returns positive scores for relevant Chinese memory using `jieba`.
- Tokenization preserves useful technical tokens such as model names, config keys, and file names.
- Tokenization splits compound technical tokens into searchable subparts.
- Chinese short-phrase recall benefits from 2-gram and 3-gram supplemental tokens.
- Single-character Chinese supplemental tokens are not generated.
- Built-in stopwords do not dominate scoring.
- A memory matching more meaningful query terms ranks ahead of a weaker match.
- A rare query term has more ranking impact than a common term.
- A long weakly related memory does not outrank a shorter highly relevant memory only because it contains many extra words.
- Empty query returns no results.
- `search_memories` still updates `usage_count` and `last_recalled_at`.
- `search_memories` still returns `MemorySearchResult`.
- Relevance remains the primary sort key over recency.

Existing CLI, UI, and chat call sites should not require behavior changes.

## Acceptance Criteria

- `mem search` uses BM25 ranking through the existing `search_memories` path.
- Chat recall uses BM25 ranking without changing chat call sites.
- UI search uses BM25 ranking without changing UI API shape.
- Existing non-search behavior is unchanged.
- Focused search tests pass.
- The full test suite passes if the environment has the required optional dependencies installed.

## Non-Goals

This is not a semantic retrieval phase. BM25 is still lexical retrieval. It should improve practical keyword recall, especially for mixed Chinese and English local memories, but it will not understand paraphrases the way embeddings or LLM reranking might.

Future semantic recall should be designed as a separate phase.
