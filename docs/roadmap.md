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

Make question answering inside `mem chat` depend more explicitly on recalled
memory.

### Features

- Keep `mem chat` as the unified user-facing QA interface.
- Recall relevant memory items before each chat response.
- Generate each answer using recalled memory and the bounded active session.
- Treat recalled memory items as the memories used for the answer in Phase 3.
- Write new experience memory after each answer.
- Write new recall memory after each answer.
- Update memory usage metadata after recall.
- Do not introduce a separate one-shot QA command.

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
- QA behavior remains unified under `mem chat`.

## Phase 3.5: Timestamp-Aware Memory Resolution

### Goal

Keep memory append-only while reducing the chance that older relevant memories
dominate the final QA context.

This phase introduces a resolver layer after relevance recall and before chat
prompt construction. The resolver uses `created_at` only within already
relevant candidates. It does not delete, overwrite, or mutate old memories.

### Core Rule

The system should not delete memories to resolve conflict.

When multiple relevant memories are available, newer memories should be
preferred as primary QA context. Older relevant memories remain available as
background context and trace evidence.

### Recall Flow

Phase 3.5 uses broad relevance recall followed by deterministic time-aware
resolution:

```text
query
  -> relevance recall with candidate_k
  -> timestamp-aware resolver
  -> final context with final_k or token budget
```

The candidate pool should be larger than the final context:

```text
candidate_k > final_k
```

This helps newer relevant memories enter the resolver even when they would not
fit in the old final top-k.

### Candidate Selection Constraint

Phase 3.5 should not add recent-only retrieval.

Candidate memories must come from relevance recall. Recency is used only after
the relevance candidate pool has already been selected.

This means the resolver does not solve cases where a newer memory is not
retrieved by relevance search at all. That limitation belongs to the search
layer and can be addressed later through semantic recall, subject indexes, or
memory graph relations.

### Resolver Output

The resolver should classify the relevance candidates for the current query
into temporary context roles:

- `primary`: newest valid-time relevant memories that should be prioritized in
  the final answer context;
- `older_relevant`: valid-time relevant memories that are older than the
  primary set and should be treated as background or trace context;
- `unresolved_time`: relevant memories whose `created_at` timestamp is missing
  or cannot be parsed.

These roles are not permanent memory states. The same memory can be `primary`
for one query and `older_relevant` for another query.

### Features

- Add a timestamp-aware resolver layer.
- Use `created_at` after relevance recall to order valid-time candidates.
- Keep old memories inspectable instead of deleting them.
- Distinguish primary, older relevant, and timestamp-unresolved memories in
  chat prompt context.
- Keep `mem search` behavior unchanged in this phase.
- Prefer explicit configuration for `recall_candidate_k`.

### Out of Scope

- Recent-only candidate retrieval.
- External search.
- Semantic embeddings.
- Vector database integration.
- Memory graph reasoning.
- Automatic contradiction detection.
- Automatic mutation of old memory state.
- Deletion or overwrite of old memories.

### Success Criteria

- Newer valid-time relevant candidates are prioritized as primary context.
- Older valid-time relevant candidates remain available as older relevant
  context.
- Timestamp-invalid relevant candidates are separated as unresolved-time
  context.
- Chat prompt construction can distinguish these context roles.
- The resolver does not mutate or delete stored memories.
- `mem search` remains unchanged.

## Phase 4: External Knowledge Acquisition

### Goal

Acquire external knowledge only when existing memory is insufficient.

External acquisition is not a single search step. When recalled memory is not
sufficient, the system should enter a model-driven acquisition loop:

```text
search -> judge -> search -> judge -> ...
```

The loop terminates only when the judge model determines that either:

- enough information has been acquired to answer the query; or
- enough information cannot be acquired with the available tools and sources.

The loop should also have a configured maximum number of search rounds so that
external acquisition cannot run indefinitely.

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
- Model-driven external search loop.
- Search model that can call configured acquisition tools.
- Judge model that evaluates whether acquired information is sufficient.
- Search, webpage, or document acquisition tools exposed to the search model.
- Source reference storage.
- External knowledge processing into knowledge memory.
- Experience memory recording how external knowledge was used.

### Model Roles

Phase 4 introduces two additional configurable model roles:

- **search model**: decides which acquisition tools to call, how to query them,
  and what candidate external information to collect;
- **judge model**: evaluates recalled memory plus acquired external information
  and decides whether to answer, continue searching, or stop because sufficient
  information is not obtainable.

Both model names should be configured in the local runtime config. The search
model and judge model may use the same provider as the chat and formation
models, or different providers when useful.

The runtime config should also include a maximum search round count for the
acquisition loop.

### Acquisition Loop

The acquisition loop starts only after memory recall and sufficiency checking
find that existing memory is not enough.

Each loop iteration should:

1. give the search model the original query, recalled memory, current
   insufficiency reasons, previous acquired evidence, and available tools;
2. let the search model call one or more acquisition tools;
3. store source references and extracted candidate evidence;
4. ask the judge model whether the accumulated memory and external evidence are
   sufficient;
5. continue searching only if the judge model identifies remaining information
   gaps that may still be fillable.

The loop must stop when the judge model returns one of two terminal decisions:

- `sufficient`: answer with the accumulated memory and external evidence;
- `not_obtainable`: answer with a clear explanation of what information is
  missing and why the available tools or sources cannot provide enough support.

The loop must also stop when the configured maximum search round count is
reached. In that case, the judge model should make a final decision using the
evidence already collected and record whether the result is sufficient,
uncertain, or not obtainable.

Non-terminal decisions should include explicit missing information and suggested
next acquisition directions.

### Storage Rule

External sources should not be stored as full raw text by default.

The system stores:

- source reference;
- processed knowledge memory;
- usage context as experience memory;
- recall, acquisition, or answer traces when useful.

Failed or incomplete acquisition attempts should also be written as memory with
state metadata such as `failed` or `uncertain`. This includes the query, missing
information, tools attempted, source references, and the judge model's terminal
reason.

### Success Criteria

- External knowledge is not always used.
- External acquisition is explainable through insufficiency reasons.
- The search-judge loop stops when information is sufficient or not obtainable.
- Search and judge model names are configurable.
- Maximum search rounds are configurable and enforced.
- Search is driven by a model with explicit tool access.
- Judge decisions are recorded and inspectable.
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
