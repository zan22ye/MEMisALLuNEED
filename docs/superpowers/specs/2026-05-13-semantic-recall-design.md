# Semantic Recall Design

Date: 2026-05-13

## Goal

Introduce semantic recall as a Phase 5 submodule for MEMisALLuNEED.

The first version should make `mem search` and `mem chat` use hybrid recall by default: BM25 lexical recall plus semantic vector recall, fused with Reciprocal Rank Fusion. It should keep SQLite as the canonical memory store and keep semantic vectors in a dedicated local index outside the `memories` table.

This design intentionally focuses on semantic recall only. It does not implement memory graph relations, UI changes, or a formal evaluation dataset.

## Current Behavior

The current search path uses BM25 lexical recall through `memisalluneed/search.py`.

Current properties:

- `search_memories(store, query, top_k)` is the public recall entry point used by CLI search, chat recall, and UI search.
- BM25 uses a recall-oriented tokenizer with English, technical token, Chinese `jieba`, and Chinese n-gram support.
- Search updates `usage_count` and `last_recalled_at` for returned memories.
- `mem chat` uses broad BM25 candidate recall, then timestamp-aware resolution.
- SQLite stores memory records, but no embeddings.

BM25 is useful for exact terms, identifiers, commands, model names, file names, and technical strings. It does not solve paraphrase or semantic similarity recall. Semantic recall should cover that gap without weakening the existing lexical behavior.

## Scope

In scope:

- Add semantic recall as a Phase 5 submodule.
- Add an `EmbeddingModel` role and OpenAI-compatible embedding client.
- Add a `SemanticIndex` abstraction.
- Add a local file-backed semantic index under `.memisalluneed/semantic_index/`.
- Add SQLite tables for semantic index status and metadata, separate from `memories`.
- Add incremental semantic indexing after memory writes.
- Add `mem semantic-index rebuild`.
- Add recall routing for `bm25`, `semantic`, and `hybrid`.
- Make `hybrid` the default recall mode for `mem search` and `mem chat`.
- Fuse BM25 and semantic candidates with Reciprocal Rank Fusion.
- Preserve fallback behavior when hybrid semantic recall is unavailable.
- Add focused unit and integration tests for configuration, indexing, rebuild, failure handling, fusion, and chat/search routing.

Out of scope:

- Adding an `embedding` column to the SQLite `memories` table.
- Storing vector values in the `memories` table.
- MEMisALLuNEED-owned web search, crawling, or external acquisition.
- Memory graph relations such as `supports`, `contradicts`, or `supersedes`.
- UI changes.
- Formal recall datasets, recall@k, MRR, or benchmark reports.
- LLM reranking.
- FAISS, Chroma, LanceDB, or another production vector database as the first implementation.
- Destructive memory mutation as a conflict-resolution strategy.

## Architecture

SQLite remains the canonical memory store. Semantic recall adds an independent recall index that can be deleted and rebuilt from SQLite.

The main modules should be:

```text
memisalluneed/
  search.py          # existing BM25 lexical recall
  semantic.py        # embedding model client, semantic index, semantic search
  recall.py          # recall mode routing and hybrid RRF fusion
  store.py           # memories table plus semantic status table helpers
```

The intended write flow is:

```text
memory write
  -> SQLite memories write succeeds
  -> semantic indexer attempts embedding
  -> local semantic index file is updated
  -> SQLite semantic status table records indexed or failed
```

The intended query flow is:

```text
query
  -> BM25 recall
  -> semantic recall
  -> RRF fusion
  -> timestamp-aware resolver
  -> search output or chat context
```

`mem chat` should continue using timestamp-aware resolution after recall. Semantic recall changes candidate selection, not the resolver's responsibility.

## Configuration

Add a model role for embeddings:

```toml
[embedding_model]
provider = "openai"
model = "text-embedding-3-small"
```

This role reuses the existing provider configuration shape:

```toml
[providers.openai]
api_key_env = "OPENAI_API_KEY"
base_url = "https://api.openai.com/v1"
```

Add recall configuration outside `[session]` so session limits do not absorb recall policy:

```toml
[recall]
mode = "hybrid"
semantic_top_k = 50
bm25_top_k = 50
rrf_k = 60
```

Allowed modes:

- `bm25`: use only lexical BM25 recall.
- `semantic`: use only semantic vector recall.
- `hybrid`: use BM25 and semantic recall, then fuse candidates with RRF.

Default behavior should be `hybrid`.

If `mode = "hybrid"` and semantic recall is unavailable, the system should degrade to BM25 and emit a clear warning through the relevant interface. If `mode = "semantic"` and semantic recall is unavailable, the system should fail clearly because the user explicitly requested semantic-only recall.

## Embedding Model

Add an embedding model interface:

```python
class EmbeddingModel:
    def embed(self, texts: list[str]) -> list[list[float]]:
        ...
```

The first implementation should be OpenAI-compatible and parallel the existing chat completion provider style, but call an embeddings endpoint instead of chat completions.

The embedding client should:

- read API keys from the configured provider's `api_key_env`;
- send batches of texts when possible;
- return one vector per input text;
- validate that returned vectors are numeric and have consistent dimensions;
- raise clear errors for missing API keys, upstream errors, malformed responses, and dimension mismatches.

Memory writes should not depend on embedding success. Embedding is part of the semantic index update path, not part of the canonical memory write guarantee.

## Semantic Index

Define a semantic index abstraction:

```python
class SemanticIndex:
    def add(self, memory_id: str, vector: list[float]) -> None:
        ...

    def search(self, query_vector: list[float], top_k: int) -> list[SemanticSearchResult]:
        ...

    def rebuild(self, entries: list[SemanticIndexEntry]) -> None:
        ...
```

The first concrete implementation should be a local file-backed brute-force index under:

```text
.memisalluneed/semantic_index/
```

The index file should store vector values outside SQLite. The exact file format can be simple and local, such as JSONL or another deterministic file format that is easy to load in tests. It should be treated as a rebuildable recall index, not as the source of truth.

Semantic search should use cosine similarity or normalized dot product. The index should validate vector dimensions so vectors from different embedding models are not mixed.

## SQLite Status Tables

Do not modify the `memories` table to add embeddings.

Add independent SQLite tables for semantic index state. A minimal shape is:

```text
semantic_index_entries
  memory_id TEXT PRIMARY KEY
  status TEXT NOT NULL        -- indexed | failed | stale | missing
  embedding_provider TEXT NOT NULL
  embedding_model TEXT NOT NULL
  embedding_dimension INTEGER
  content_hash TEXT NOT NULL
  indexed_at TEXT
  error TEXT
  updated_at TEXT NOT NULL

semantic_index_metadata
  key TEXT PRIMARY KEY
  value TEXT NOT NULL
```

The status table records whether each memory has a current semantic vector. The vector itself remains in the local semantic index file.

`content_hash` should be derived from memory content and any other text fields included in embedding input. It lets the system detect stale entries after content, embedding model, index version, or embedding input format changes.

## Indexing Strategy

Use eventual consistency.

When a memory is written:

1. The memory is written to SQLite first.
2. The semantic indexer tries to embed the memory text.
3. If embedding and index write succeed, the status table records `indexed`.
4. If embedding or index write fails, the memory remains written and the status table records `failed` with an error.

The system must not roll back a successful memory write because embedding or semantic index writing failed.

This rule should apply to:

- `mem add`;
- chat rolling formation writes;
- chat exit flush writes;
- host-supplied source, evidence, and answer trace integration writes;
- UI/API memory writes if those routes continue to use shared memory write helpers.

## Rebuild Command

Add a minimal maintenance command:

```bash
mem semantic-index rebuild
```

The rebuild command should:

- initialize the semantic index directory if needed;
- read all memories from SQLite;
- generate embeddings with the configured embedding model;
- replace or rewrite the local semantic index file;
- update semantic status rows for indexed memories;
- mark failed rows with clear errors if embedding or write failures occur;
- make it possible to recover from missing, failed, stale, corrupted, or deleted local index files.

The command should be safe to rerun. Rebuild should treat SQLite memory records as the source of truth.

This spec does not require `status`, `doctor`, or other semantic-index subcommands in the first version.

## Recall Routing

Add a unified recall layer so callers do not need to know whether recall is BM25, semantic, or hybrid.

Recommended shape:

```python
@dataclass(frozen=True)
class RecallResult:
    item: MemoryItem
    score: float
    source: str
    scores: dict[str, object]


def recall_memories(
    store: MemoryStore,
    query: str,
    *,
    config: AppConfig,
    top_k: int,
) -> list[RecallResult]:
    ...
```

Mode behavior:

- `bm25`: call the existing BM25 scorer.
- `semantic`: embed the query and search the semantic index.
- `hybrid`: run BM25 and semantic recall, then fuse candidates with RRF.

`search_memories` currently updates recall metadata. With a unified recall layer, recall metadata should be updated only for the final returned results, not for every intermediate candidate from each retriever.

If compatibility requires `search_memories` to remain public for BM25 tests and existing call sites, it can stay as the BM25-specific helper. Production CLI/chat paths should move to `recall_memories`.

## Hybrid Fusion

Hybrid recall should use Reciprocal Rank Fusion:

```text
rrf_score(memory) = sum(1 / (rrf_k + rank_in_retriever))
```

where `rank_in_retriever` starts at 1 for the top result in each retriever.

RRF is preferred for the first version because BM25 scores and cosine similarities are not directly comparable. Ranking-based fusion avoids brittle score normalization.

The result metadata should preserve enough information for debugging and future observability:

```python
scores = {
    "bm25_rank": 3,
    "semantic_rank": 1,
    "rrf_score": 0.031,
}
```

`RecallResult.source` should be:

- `bm25` for BM25-only mode;
- `semantic` for semantic-only mode;
- `hybrid` for fused results.

## CLI Behavior

Keep CLI changes minimal.

Required new command:

```bash
mem semantic-index rebuild
```

`mem search` should use the configured default recall mode. Since the chosen first version is configuration-first, this spec does not require adding `--mode`, `--semantic`, or `--hybrid` flags.

`mem chat` should also use the configured default recall mode. It should still:

- retrieve a broad candidate pool;
- pass final candidates through timestamp-aware resolution;
- record used memory ids for memories actually supplied to the chat prompt.

## Error Handling

Semantic indexing failures should not prevent canonical memory writes.

Expected failure handling:

- Missing embedding API key during memory write: write memory, mark semantic index entry `failed`, record a clear error.
- Missing embedding API key during `semantic-index rebuild`: command fails clearly or records failures for all affected rows, depending on implementation structure.
- Semantic index file missing in `hybrid` mode: degrade to BM25 with a warning.
- Semantic index file missing in `semantic` mode: fail clearly.
- Embedding dimension mismatch: mark affected entry failed and require rebuild after model/config correction.
- Corrupt local index file: fail semantic recall clearly and allow `semantic-index rebuild` to repair it.

Warnings should be visible in CLI paths. Library functions should expose structured errors or result metadata so callers can decide how to display them.

## Tests

Required test coverage:

- Config reads `[embedding_model]`.
- Config reads `[recall]`.
- Invalid `recall.mode` is rejected.
- The SQLite `memories` table does not gain an `embedding` column.
- Semantic status tables are initialized separately from `memories`.
- Local semantic index can add, save, load, and search vectors.
- Local semantic index rejects inconsistent vector dimensions.
- Rebuild creates semantic index entries from SQLite memories.
- Rebuild is safe to rerun.
- Incremental indexing runs after memory writes through shared write paths.
- Embedding failure does not roll back memory writes.
- Embedding failure records a failed semantic status row with an error.
- Hybrid recall uses RRF and can include candidates found by only one retriever.
- Recall metadata updates only final returned memories.
- `mem search` uses the unified recall path and defaults to hybrid when configured.
- `mem chat` uses the unified recall path and still passes results through timestamp-aware resolution.
- Hybrid mode degrades to BM25 when semantic recall is unavailable.
- Semantic-only mode fails clearly when semantic recall is unavailable.
- UI routes do not change behavior in this first version.

Optional tests can use a fake embedding model with deterministic vectors. Real embedding provider tests should be marked and skipped unless explicitly enabled.

## Acceptance Criteria

- `mem search` defaults to hybrid recall when config uses `mode = "hybrid"`.
- `mem chat` defaults to hybrid recall when config uses `mode = "hybrid"`.
- `mem semantic-index rebuild` rebuilds the local semantic index from SQLite memories.
- Memory writes succeed even if semantic indexing fails.
- Semantic indexing failures are recorded in SQLite status tables.
- The local semantic index can be deleted and rebuilt from SQLite.
- Semantic vector values are not stored in the `memories` table.
- SQLite remains the canonical structured memory store.
- Existing BM25-focused tests continue to pass.
- New semantic recall tests pass.
- No MEMisALLuNEED-owned web search or external acquisition is introduced.

## Future Work

Later phases may add:

- FAISS, Chroma, LanceDB, or another dedicated vector index implementation behind `SemanticIndex`.
- UI controls and observability for recall mode, semantic status, and hybrid fusion traces.
- Evaluation datasets comparing BM25, semantic, and hybrid recall.
- Metrics such as recall@k, MRR, answer quality, and memory growth efficiency.
- Memory graph integration where semantic recall candidates are expanded or constrained by explicit relations.
- Background retry jobs for failed semantic indexing.
