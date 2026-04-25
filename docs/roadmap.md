# MEMisALLuNEED Roadmap

This document records the current implementation plan for MEMisALLuNEED.

The project is designed as a Memory-Centric Agent: a system whose primary substrate is a continuously growing memory space rather than an ever-growing context window.

## Core Direction

MEMisALLuNEED is based on the following assumptions:

1. Everything before the current moment can be treated as memory.
2. For a query, the system first needs sufficiently relevant memory.
3. External knowledge is acquired only when existing memory is insufficient.
4. Every query, answer, recall event, external knowledge use, failure, and correction can become memory.
5. Memory is automatically written after being cleaned, compressed, and structured.
6. Active sessions are bounded by the latest `k` turns or `k` tokens.
7. Older session context must be transformed into memory and later reused through recall.

## Phase 0: Concept and Spec

### Goal

Define the theory, vocabulary, boundaries, and first system design.

### Deliverables

- `README.md`
- `README_zh.md`
- `docs/roadmap.md`
- Future concept and architecture documents

### Scope

This phase focuses on writing down the project thesis and design direction.

### Out of Scope

- Runtime implementation
- LLM integration
- External knowledge acquisition
- Evaluation benchmark

### Success Criteria

- The project has a clear conceptual definition.
- The main memory types are documented.
- The high-level implementation phases are documented.
- The first runnable prototype scope is clear.

## Phase 1: CLI Memory Substrate

### Goal

Build the minimal runnable memory system as a command-line demo.

The purpose of this phase is to prove that memory items can be created, stored, recalled, inspected, and exported.

### Interface

Initial CLI commands:

- `mem init`: initialize a local memory database.
- `mem add`: add a memory item.
- `mem list`: list stored memory items.
- `mem show <id>`: inspect one memory item.
- `mem search <query>`: recall relevant memory items.
- `mem export`: export memory items to JSONL.

### Storage

Use **SQLite as the primary memory substrate** and **JSONL as the export format**.

SQLite is recommended because it supports structured metadata, updates, relations, and future graph edges without introducing a heavy dependency too early.

JSONL is retained because it is transparent, easy to inspect, easy to back up, and useful for evaluation.

### Initial Tables

Phase 1 should start with a `memories` table:

- `id`
- `type`
- `content`
- `state`
- `confidence`
- `metadata`
- `created_at`
- `updated_at`
- `usage_count`
- `last_recalled_at`

It should also reserve room for a future `memory_edges` table:

- `id`
- `source_memory_id`
- `target_memory_id`
- `relation_type`
- `metadata`
- `created_at`

The graph table can be created early or postponed, but the architecture should not block it.

### Core Modules

Suggested Python package layout:

```text
MEMisALLuNEED/
  pyproject.toml
  memisalluneed/
    __init__.py
    cli.py
    schema.py
    store.py
    search.py
    export.py
  tests/
    test_store.py
    test_search.py
```

Core objects:

- `MemoryItem`
- `MemoryStore`
- `MemorySearcher`

### Search

Phase 1 should use a lightweight text similarity baseline first.

Phase 1 should not store embeddings in SQLite.

Vector recall should be introduced later through a dedicated vector database, not through an `embedding` column in the SQLite memory table.

The initial prototype should avoid unnecessary dependencies and prove the storage-recall loop first.

### Out of Scope

- LLM-based memory cleaning
- Session rolling write
- External knowledge acquisition
- Memory graph reasoning
- Conflict detection
- Benchmarking

### Success Criteria

- A user can initialize a local database.
- A user can add memory items.
- A user can list memory items.
- A user can inspect one memory item.
- A user can search memory items with a query.
- A user can export memory items as JSONL.
- Store and search behavior have minimal tests.

## Phase 2: Session to Memory Formation

### Goal

Turn bounded sessions into automatic memory formation.

### Features

- `mem chat`: interactive session mode.
- Keep only the latest `k` turns or `k` tokens in active session context.
- Roll older context into memory when the session exceeds the limit.
- Run a lightweight per-turn memory check after each query-answer pair.
- Create memory candidates from important new information.

### Memory Formation

This phase introduces a smaller model or lightweight LLM call to clean and structure memory candidates.

The memory formation process should:

- preserve complete meaning;
- remove noise;
- reduce redundancy;
- extract knowledge memory;
- extract experience memory;
- generate recall memory where useful;
- assign state and metadata.

### Out of Scope

- Full external knowledge acquisition
- Advanced memory graph reasoning
- Formal benchmark

### Success Criteria

- Session context does not grow without bound.
- Older context is transformed into memory.
- Important per-turn information is automatically written.
- Older session information can be found again through recall.

## Phase 3: Memory-Centric QA Loop

### Goal

Make query answering depend on recalled memory.

### Features

- `mem ask <query>`: ask a question through the memory system.
- Recall relevant memory items for the query.
- Generate an answer using recalled memory.
- Record which memories were used.
- Write new experience memory after answering.
- Write new recall memory after answering.
- Update memory usage metadata.

### Metadata Updates

The system should update:

- `usage_count`
- `last_recalled_at`
- answer-to-memory usage links
- recall trace metadata

### Out of Scope

- External search by default
- Heavy graph reasoning
- Benchmarking

### Success Criteria

- Answers show which memory items were used.
- Each answer creates new reusable memory.
- Recall traces can be inspected.
- Memory usage metadata changes over time.

## Phase 4: External Knowledge Acquisition

### Goal

Acquire external knowledge only when existing memory is insufficient.

### Sufficiency Check

External knowledge should be triggered when:

- relevant memory cannot be found;
- recalled memory has low confidence;
- recalled memories conflict;
- the query requires fresh or time-sensitive information;
- existing memory lacks evidence;
- existing memory only partially covers the query.

### Features

- Memory sufficiency checker.
- Search, webpage, or document acquisition interface.
- Source reference storage.
- External knowledge processing into knowledge memory.
- Experience memory recording how external knowledge was used.

### Storage Rule

External sources should not be stored as full raw text by default.

The system stores:

- source reference;
- processed knowledge memory;
- usage context as experience memory;
- recall or answer traces when useful.

### Success Criteria

- External knowledge is not always used.
- External acquisition is explainable through insufficiency reasons.
- Source references are stored.
- Acquired knowledge becomes reusable memory.

## Phase 5: Memory Graph and Evaluation

### Goal

Turn the prototype into a research-oriented system with observable memory growth and evaluation.

This phase can also introduce a dedicated vector database for scalable semantic recall.

Vector search should be treated as a separate recall index that works alongside the canonical SQLite memory store. SQLite remains the source of truth for memory metadata and structured records; the vector database stores and searches vector representations.

### Memory Graph

Introduce explicit memory relations:

- `supports`
- `contradicts`
- `derived_from`
- `updates`
- `supersedes`
- `recalled_with`
- `used_in`

### Evaluation

Compare MEMisALLuNEED against simpler baselines:

- normal chat context;
- static RAG;
- chat memory without recall traces;
- memory-centric recall with graph relations.

### Possible Metrics

- answer quality;
- recall relevance;
- source usage quality;
- ability to reuse prior experience;
- robustness to long sessions;
- handling of contradictions;
- memory growth efficiency.

### Success Criteria

- Memory graph growth can be inspected.
- Conflicts and updates can be represented.
- The system can be compared against baseline approaches.
- The project can support research-style experiments.

## Recommended First Implementation

Start with Phase 1 as a small CLI demo.

Do not introduce LLM memory formation, external search, or graph reasoning in the first implementation. Keep the first milestone focused on the storage-recall-export loop.

The first runnable milestone should prove:

> A memory item can be written, persisted, recalled, inspected, and exported.
