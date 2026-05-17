# MEMisALLuNEED Roadmap

This document records the current implementation roadmap and status ledger for
MEMisALLuNEED.

The project is designed as a Memory-Centric Agent: a system whose primary
substrate is a continuously growing memory space rather than an ever-growing
context window.

## Core Direction

MEMisALLuNEED is based on the following assumptions:

1. Everything before the current moment can be treated as memory.
2. For a query, the system first needs sufficiently relevant memory.
3. External knowledge is acquired only when existing memory is insufficient.
4. Every query, answer, recall event, external knowledge use, failure, and
   correction can become memory.
5. Memory is automatically written after being cleaned, compressed, and
   structured.
6. Active sessions are bounded by the latest `k` turns or `k` tokens.
7. Older session context must be transformed into memory and later reused
   through recall.

## Current Status Snapshot

### Implemented Phases

The project has implemented:

- Phase 1: CLI memory substrate.
- Phase 2: session-to-memory formation.
- Phase 3: memory-centric QA loop.
- Phase 3.5: timestamp-aware memory resolution.
- Phase 4: host-supplied knowledge integration.

Phase 5, memory graph and evaluation, is the next major roadmap phase.

The first public release target is `v0.1.0`. Its intended scope is:

- Phase 5.1: semantic recall and hybrid retrieval;
- Phase 5.2: chat observability workbench;
- Phase 5.3: FastAPI platform service and OpenClaw reference adapter;
- Phase 5.4: code review, cleanup, and release hardening.

Memory decay and stronger time-aware filtering are planned after `v0.1.0`.

### Current CLI Surface

Current commands include:

- `mem init`
- `mem add`
- `mem list`
- `mem show <id>`
- `mem search <query>`
- `mem export`
- `mem chat`
- `mem ui`
- `mem integrate-source`
- `mem integrate-evidence`
- `mem integrate-answer`

### Current Storage and Recall

SQLite is the canonical structured memory store. JSONL remains the transparent
export format.

`mem search`, chat recall, and UI search use BM25 lexical recall with a
recall-oriented tokenizer. The tokenizer supports English, technical tokens,
Chinese segmentation when `jieba` is available, and Chinese n-gram fallback.

The current system does not use embeddings or a vector database. Future semantic
recall should use a dedicated vector index or vector database, not an
`embedding` column in the SQLite `memories` table.

### Current Reliability Baseline

Runtime reliability mitigations have landed for:

- atomic JSON writes for local session and formation job files;
- process-local formation job locking;
- flush and worker idempotency to reduce duplicate formation;
- SQLite WAL and busy-timeout configuration;
- structured UI error mapping;
- short-lived HTTP client lifecycle when the model creates its own client;
- focused reliability tests.

Recent validation evidence recorded for the repository:

- `uv run --with pytest --with jieba --with httpx pytest -q` passed with 139
  tests and 8 skipped real-model tests.
- BM25 search tests passed with 14 tests.
- Runtime reliability tests passed with 12 tests.
- `mem --help` shows chat, UI, and host integration commands.

## Phase 0: Concept and Spec

### Status

Implemented.

### Goal

Define the theory, vocabulary, boundaries, and first system design.

### Delivered

- `README.md`
- `README_zh.md`
- `docs/roadmap.md`
- phase specs and implementation plans under `docs/`

### Scope

This phase focused on writing down the project thesis and design direction.

### Out of Scope

- Runtime implementation.
- LLM integration.
- External knowledge acquisition.
- Evaluation benchmark.

### Success Criteria

- The project has a clear conceptual definition.
- The main memory types are documented.
- The high-level implementation phases are documented.
- The first runnable prototype scope is clear.

## Phase 1: CLI Memory Substrate

### Status

Implemented.

### Goal

Build the minimal runnable memory system as a command-line demo.

The purpose of this phase was to prove that memory items can be created,
stored, recalled, inspected, and exported.

### Delivered Interface

- `mem init`: initialize a local memory database.
- `mem add`: add a memory item.
- `mem list`: list stored memory items.
- `mem show <id>`: inspect one memory item.
- `mem search <query>`: recall relevant memory items.
- `mem export`: export memory items to JSONL.

### Storage

Use SQLite as the primary memory substrate and JSONL as the export format.

SQLite is used because it supports structured metadata, updates, relations, and
future graph edges without introducing a heavy dependency too early.

JSONL is retained because it is transparent, easy to inspect, easy to back up,
and useful for evaluation.

### Core Tables

The initial `memories` table includes:

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

The architecture reserves room for a future `memory_edges` table:

- `id`
- `source_memory_id`
- `target_memory_id`
- `relation_type`
- `metadata`
- `created_at`

The graph table can be created during Phase 5, but the architecture should not
block it.

### Core Modules

Current package layout includes:

```text
memisalluneed/
  __init__.py
  cli.py
  config.py
  schema.py
  store.py
  search.py
  export.py
  formation.py
  formation_jobs.py
  integration.py
  resolution.py
  session.py
  ui_server.py
```

Core objects include:

- `MemoryItem`
- `MemoryStore`
- search and recall result helpers
- formation and integration helpers

### Search

Phase 1 started with a lightweight text similarity baseline. The current system
has since replaced that baseline with BM25 lexical recall.

Phase 1 did not store embeddings in SQLite, and this remains a standing rule.
Vector recall should be introduced through a dedicated vector database or vector
index, not through an `embedding` column in the SQLite memory table.

### Out of Scope

- LLM-based memory cleaning.
- Session rolling write.
- External knowledge acquisition.
- Memory graph reasoning.
- Conflict detection.
- Benchmarking.

### Success Criteria

- A user can initialize a local database.
- A user can add memory items.
- A user can list memory items.
- A user can inspect one memory item.
- A user can search memory items with a query.
- A user can export memory items as JSONL.
- Store and search behavior have tests.

## Phase 2: Session to Memory Formation

### Status

Implemented.

### Goal

Turn bounded sessions into automatic memory formation.

### Delivered Features

- `mem chat`: interactive session mode.
- Keep only the latest `k` turns or `k` tokens in active session context.
- Roll older context into memory when the session exceeds the limit.
- Flush remaining session content into memory when the session exits.
- Run lightweight memory formation over session turns.
- Create memory candidates from important new information.

### Memory Formation

This phase introduced formation-model-backed cleaning and structuring for memory
candidates.

The memory formation process should:

- preserve complete meaning;
- remove noise;
- reduce redundancy;
- extract knowledge memory;
- extract experience memory;
- generate recall memory where useful;
- assign state and metadata.

### Out of Scope

- Full external knowledge acquisition.
- Advanced memory graph reasoning.
- Formal benchmark.

### Success Criteria

- Session context does not grow without bound.
- Older context is transformed into memory.
- Important per-turn information is automatically written.
- Older session information can be found again through recall.

## Phase 3: Memory-Centric QA Loop

### Status

Implemented as memory-centric QA behavior inside `mem chat`.

### Goal

Make question answering inside `mem chat` depend more explicitly on recalled
memory.

### Delivered Features

- Keep `mem chat` as the unified user-facing QA interface.
- Recall relevant memory items before each chat response.
- Generate each answer using recalled memory and the bounded active session.
- Treat recalled memory items as the memories used for the answer in Phase 3.
- Optionally display used memory trace with `mem chat --show-memory-trace`.
- Form rolled and flushed chat turns with `formation_kind = "chat_qa"`.
- Preserve recall trace metadata through `recalled_memory_ids` and
  `used_memory_ids`.
- Process rolling formation and exit flush formation one turn at a time.
- Allow `experience`, `knowledge`, and `recall` memories when useful.
- Update memory usage metadata after recall.
- Do not introduce a separate one-shot QA command.
- Do not write `source` memories in Phase 3.
- Do not perform immediate memory formation after every assistant response.

### Metadata Updates

The system updates:

- `usage_count`
- `last_recalled_at`
- recall trace metadata in formed memory items

### Out of Scope

- External search by default.
- Source memory writing.
- Heavy graph reasoning.
- Benchmarking.

### Success Criteria

- Answers can show which memory items were used when
  `--show-memory-trace` is enabled.
- Each formed `chat_qa` turn can create reusable experience memory.
- Recall traces can be inspected.
- Memory usage metadata changes over time.
- QA behavior remains unified under `mem chat`.

## Phase 3.5: Timestamp-Aware Memory Resolution

### Status

Implemented as deterministic timestamp-aware resolution for `mem chat`.

### Goal

Keep memory append-only while reducing the chance that older relevant memories
dominate the final QA context.

This phase introduced a resolver layer after relevance recall and before chat
prompt construction. The resolver uses `created_at` only within already relevant
candidates. It does not delete, overwrite, or mutate old memories.

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

Phase 3.5 does not add recent-only retrieval.

Candidate memories must come from relevance recall. Recency is used only after
the relevance candidate pool has already been selected.

This means the resolver does not solve cases where a newer memory is not
retrieved by relevance search at all. That limitation belongs to the search
layer and can be addressed later through semantic recall, subject indexes, or
memory graph relations.

### Resolver Output

The resolver classifies relevance candidates for the current query into
temporary context roles:

- `primary`: newest valid-time relevant memories that should be prioritized in
  the final answer context;
- `older_relevant`: valid-time relevant memories that are older than the
  primary set and should be treated as background or trace context;
- `unresolved_time`: relevant memories whose `created_at` timestamp is missing
  or cannot be parsed.

These roles are not permanent memory states. The same memory can be `primary`
for one query and `older_relevant` for another query.

### Delivered Features

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

## Phase 4: Host-Supplied Knowledge Integration

### Status

Implemented as formation-model-backed host-supplied integration APIs with CLI
wrappers.

### Goal

Integrate external knowledge that is supplied by the host application.

MEMisALLuNEED is a memory plugin, not a full external-search agent. It should
not decide whether outside knowledge is needed, search the web, call external
tools, or judge whether acquired information is sufficient.

The host application owns those decisions. MEMisALLuNEED receives what the host
already decided to provide and turns it into structured, reusable memory.

### Plugin Boundary

MEMisALLuNEED should not implement:

- memory sufficiency checking;
- insufficiency reasons;
- deciding whether external knowledge is needed;
- external search;
- search model roles;
- judge model roles;
- search-judge loops;
- web browsing;
- document crawling;
- external tool calling.

The host application is responsible for:

- deciding whether memory is enough;
- deciding whether outside knowledge is needed;
- acquiring external evidence;
- selecting tools and sources;
- judging whether evidence is sufficient for its answer.

MEMisALLuNEED is responsible for remembering what the host supplies.

### Integration Flow

The intended flow is:

```text
host application
  -> decides external knowledge is needed
  -> acquires evidence or source references
  -> provides query, evidence, source refs, answer trace, and metadata
  -> MEMisALLuNEED forms reusable memory
```

### Delivered Features

- Host-supplied source reference storage.
- Host-supplied evidence ingestion.
- Processed knowledge memory from host-supplied evidence.
- Experience memory recording how host-supplied evidence was used.
- Answer trace memory when the host provides answer/evidence relationships.
- Provenance metadata for source, host, query, answer, and evidence ids.
- Failed, uncertain, incomplete, or contradicted host-supplied knowledge can be
  written with state metadata when the host marks it that way.

### Interfaces

Phase 4 exposes CLI wrappers such as:

```text
mem integrate-source
mem integrate-evidence
mem integrate-answer
```

and library integration helpers such as:

```python
integrate_source_reference(...)
integrate_host_evidence(...)
integrate_answer_trace(...)
```

### Metadata

Host-supplied integration preserves metadata such as:

- `source = "host_supplied"`;
- `source_uri`;
- `source_title`;
- `retrieved_at`;
- `host_agent`;
- `query`;
- `answer_id`;
- `evidence_ids`;
- `formation_kind`.

### Storage Rule

External sources should not be stored as full raw text by default.

The system stores:

- source reference memory;
- processed knowledge memory;
- usage context as experience memory;
- answer, evidence, and provenance traces when useful.

The host may provide failed, uncertain, incomplete, contradicted, or outdated
evidence. MEMisALLuNEED should preserve those states when forming memory, but it
should not independently decide that evidence is sufficient or insufficient.

### Success Criteria

- The plugin can accept host-supplied source references.
- The plugin can accept host-supplied evidence.
- The plugin can form source reference, knowledge, and experience memories from
  host-supplied inputs.
- Provenance metadata is preserved.
- External source full text is not stored by default.
- The plugin does not perform external search.
- The plugin does not implement sufficiency checks or insufficiency reasons.
- The plugin does not implement search or judge model roles.
- The plugin does not implement a search-judge acquisition loop.

## Cross-Phase Improvements Already Landed

### BM25 Lexical Recall

BM25 replaced the original token-overlap search baseline. This improved local
lexical recall while preserving a lightweight, inspectable implementation.

BM25 is still lexical recall. It is useful for exact terms, identifiers,
commands, model names, file names, mixed Chinese and English memories, and
technical strings. It does not solve paraphrase or semantic similarity recall.

### Runtime Reliability Mitigations

The runtime reliability work improved local correctness and debuggability
without changing the project boundary. It did not add external acquisition,
semantic search, graph reasoning, or destructive memory mutation.

### Local UI and Formation Support

The local UI exists through `mem ui`. Supporting formation/runtime improvements
make session rolling, background formation, manual flush, and local debugging
more reliable, while preserving `mem chat` as the core QA interface.

## Phase 5: Memory Graph and Evaluation

### Status

Next major phase.

### Goal

Turn the prototype into a research-oriented system with observable memory
growth, explicit memory relations, and evaluation.

Phase 5 should make memory items less isolated. It should represent why memory
items relate to one another, how they were reused, and how those relations affect
recall and answers.

### Memory Graph

Introduce explicit memory relations through a canonical SQLite-backed graph
structure, such as a `memory_edges` table.

Initial relation types:

- `supports`
- `contradicts`
- `derived_from`
- `updates`
- `supersedes`
- `recalled_with`
- `used_in`

The graph should preserve append-only memory behavior by default. Contradiction,
updates, and supersession should be represented through state, metadata, and
relations rather than destructive deletion or overwrite.

### Possible Graph Interfaces

Possible CLI and/or Python interfaces include:

```text
mem graph
mem show <id> --relations
mem relate <source-id> <relation> <target-id>
```

or library helpers such as:

```python
add_memory_relation(...)
list_memory_relations(...)
get_memory_neighborhood(...)
```

These names are placeholders for the Phase 5 design. The roadmap commits to the
capability, not the exact interface spelling.

### Evaluation

Add small evaluation datasets and baselines for memory-centric behavior.

Compare MEMisALLuNEED against simpler baselines:

- normal bounded chat context;
- BM25-only memory recall;
- static RAG-style context injection;
- chat memory without recall traces;
- memory-centric recall with graph relations.

### Possible Metrics

- answer quality;
- recall relevance;
- answer grounding and trace usefulness;
- source usage quality;
- ability to reuse prior experience;
- robustness to long sessions;
- handling of contradictions;
- memory growth efficiency.

### Success Criteria

- Memory relations can be created, stored, listed, and exported.
- Relation metadata preserves provenance and formation context.
- Recall and answer traces can reference graph relations when available.
- Evaluation datasets cover long-session reuse and contradiction handling.
- Baselines can be run repeatedly with stable outputs.
- Evaluation reports show whether graph relations improve recall or answer
  grounding compared with BM25-only recall.

### Out of Scope

- MEMisALLuNEED-owned web search, crawling, or external acquisition loops.
- Storing embeddings directly in the SQLite `memories` table.
- Automatic destructive conflict resolution.
- Replacing host-owned sufficiency judgment.

## Phase 5.1: Semantic Recall and Hybrid Retrieval

### Status

Designed, not implemented.

### Goal

Add semantic recall as an explicit recall subphase so MEMisALLuNEED can find
paraphrased or semantically similar memories that BM25 may miss.

BM25 should remain the strong lexical baseline. Semantic recall should complement
it, not replace it.

### Design Rules

- Keep SQLite as the canonical structured memory store.
- Do not add an `embedding` column to the SQLite `memories` table.
- Store vectors in a dedicated local vector index or vector database.
- Support BM25-only recall for lightweight and deterministic operation.
- Support semantic-only recall when explicitly requested.
- Support hybrid recall that fuses BM25 and semantic candidates.
- Use Reciprocal Rank Fusion or another rank-based method so BM25 scores and
  vector similarities do not need brittle direct normalization.
- In hybrid mode, degrade to BM25 with a clear warning when semantic recall is
  unavailable.
- In semantic-only mode, fail clearly when semantic recall is unavailable.

### Possible Interfaces

A unified recall layer can let callers avoid knowing whether recall is lexical,
semantic, or hybrid:

```python
recall_memories(...)
```

`search_memories(...)` can remain as the BM25-specific helper for tests and
compatibility.

`mem search` and `mem chat` may later expose recall mode configuration, but the
roadmap does not require a specific CLI flag shape yet.

### Success Criteria

- Existing BM25-focused tests continue to pass.
- Semantic index build, update, missing-index, and corrupt-index behavior is
  tested.
- Hybrid recall returns fused candidates with enough metadata for debugging.
- Hybrid recall falls back to BM25 when semantic recall is unavailable.
- Semantic-only recall fails clearly when semantic recall is unavailable.
- Evaluation can compare BM25, semantic, and hybrid recall behavior.

### Out of Scope

- Memory graph integration. Graph expansion belongs to Phase 5.
- UI controls and visual traces. These belong to Phase 5.2.
- External search or source acquisition.
- Storing full raw source text by default.

## Phase 5.2: Chat Observability Workbench

### Status

Designed, not implemented.

### Goal

Improve the local UI into a practical observability workbench for chat, recall,
formation, host-supplied integration, graph relations, and evaluation traces.

The workbench should make memory-centric behavior explainable: a user should be
able to inspect why an answer used certain memories, which formation jobs ran,
which host-supplied evidence was preserved, and how future graph relations affect
recall.

### Scope

The workbench may expose:

- recalled memories and used memories for a chat response;
- timestamp resolver roles such as `primary`, `older_relevant`, and
  `unresolved_time`;
- formation jobs, statuses, failures, and retry context;
- source and evidence provenance from Phase 4;
- relation neighborhoods once Phase 5 graph support exists;
- evaluation traces once datasets and baselines exist.

### Non-Goals

- Do not turn MEMisALLuNEED into an external search UI.
- Do not move host-owned sufficiency judgment into MEMisALLuNEED.
- Do not replace the CLI as the stable automation interface.
- Do not require graph or semantic recall to be complete before improving basic
  observability.

### Success Criteria

- A user can explain which memories contributed to a response.
- A user can inspect recall, resolver, and formation traces without reading raw
  files directly.
- A user can debug failed or uncertain formation and integration paths.
- The workbench can later display graph relations and evaluation traces without
  changing the core memory model.

## Phase 5.3: FastAPI Platform Service and OpenClaw Reference Adapter

### Status

Planned for `v0.1.0`.

### Goal

Turn MEMisALLuNEED into a usable memory platform service for external host
applications, with OpenClaw as the first reference adapter scenario.

The platform service should let external tools call MEMisALLuNEED for recall,
memory writing, host-supplied evidence integration, and observability without
parsing CLI text output or depending on internal modules.

### Core Decision

FastAPI is required for the `v0.1.0` platformization work.

The FastAPI service is the external integration transport. It should be a thin
HTTP layer over a stable Python platform facade, not the place where core memory
logic lives.

The intended architecture is:

```text
OpenClaw or another host application
  -> HTTP client or adapter
  -> MEMisALLuNEED FastAPI service
  -> MemoryPlatform facade
  -> store, recall, formation, integration, observability
```

### Platform Facade

Introduce a stable Python facade such as `MemoryPlatform` to centralize
platform operations before exposing them through HTTP.

The facade should cover:

- recall context for a host query;
- remember an interaction after a host answer or action;
- integrate host-supplied source references;
- integrate host-supplied evidence;
- integrate host-supplied answer traces;
- inspect memories and traces for observability.

FastAPI routes should call this facade. They should not bypass it to manipulate
`store.py`, `search.py`, `formation.py`, `integration.py`, or `resolution.py`
directly.

### FastAPI Service

The first platform service should expose a small local HTTP API with JSON
request and response bodies.

Initial endpoint candidates:

```text
GET  /health
POST /v0/recall
POST /v0/interactions
POST /v0/sources
POST /v0/evidence
POST /v0/answers
GET  /v0/memories/{id}
GET  /v0/traces/{trace_id}
```

The exact endpoint names can be refined in the Phase 5.3 design, but the
service should provide these capability groups:

- recall API;
- memory write API;
- host knowledge integration API;
- observability API.

### OpenClaw Reference Adapter

OpenClaw is the first reference integration target.

OpenClaw remains responsible for:

- agent flow and task execution;
- tool calling;
- external search or acquisition when it chooses to do so;
- deciding whether memory is sufficient;
- deciding whether host-acquired evidence is sufficient for its answer.

MEMisALLuNEED remains responsible for:

- recalling relevant memory for OpenClaw requests;
- writing reusable memory from OpenClaw interactions;
- integrating OpenClaw-supplied sources, evidence, and answer traces;
- preserving provenance and host metadata;
- exposing traces for debugging and observability.

The adapter flow should be:

```text
before answer or task
  -> OpenClaw calls POST /v0/recall
  -> OpenClaw uses returned memory context

after answer or task
  -> OpenClaw calls POST /v0/interactions
  -> MEMisALLuNEED forms reusable memory and trace metadata

after external evidence use
  -> OpenClaw calls POST /v0/sources, /v0/evidence, or /v0/answers
  -> MEMisALLuNEED stores source references, processed knowledge, and usage context
```

### Security and Runtime Boundaries

For `v0.1.0`, the FastAPI service should be a local service by default.

- Bind to `127.0.0.1` by default.
- Do not expose a public network service by default.
- Keep database path and runtime paths explicit.
- Use structured JSON error responses.
- Avoid adding plugin execution, marketplace, or arbitrary remote code loading.
- Do not move external acquisition or sufficiency judgment into
  MEMisALLuNEED.

### Success Criteria

- OpenClaw can use MEMisALLuNEED through FastAPI without parsing CLI text.
- FastAPI routes are thin wrappers over `MemoryPlatform`.
- The service exposes JSON request and response models for recall, interaction
  write, source integration, evidence integration, answer integration, and basic
  inspection.
- Host metadata and provenance are preserved across API calls.
- The OpenClaw adapter example demonstrates before-answer recall, after-answer
  memory writing, and host evidence integration.
- FastAPI tests use an in-process test client and do not require binding a real
  public port.
- The OpenAPI schema can serve as a platform contract for future adapters.

### Out of Scope

- Full plugin runtime.
- Plugin marketplace.
- Remote multi-tenant service operation.
- MEMisALLuNEED-owned web search or crawling.
- Host sufficiency judgment.
- Replacing the CLI.

## Phase 5.4: Code Review, Cleanup, and v0.1 Release Hardening

### Status

Planned for `v0.1.0`.

### Goal

Stabilize the project for the first public release after Phase 5.1, Phase 5.2,
and Phase 5.3 are complete.

This phase should focus on review, cleanup, documentation alignment, and release
readiness rather than adding new memory behavior.

### Scope

- Perform code review of Phase 5.1, 5.2, and 5.3 changes.
- Fix correctness, reliability, API, and maintainability risks found during
  review.
- Clean up broad modules only where the cleanup directly improves release
  stability or platform API boundaries.
- Align `README.md`, `README_zh.md`, usage guides, roadmap, and examples.
- Document the FastAPI platform API and OpenClaw reference adapter.
- Document known limitations and current risks.
- Validate examples and smoke-test the release flow.
- Prepare release notes for `v0.1.0`.

### Success Criteria

- Full local tests pass.
- Focused Phase 5.1, 5.2, and 5.3 tests pass.
- FastAPI platform API tests pass.
- OpenClaw adapter example is documented and validated.
- Public docs describe the v0.1 platform boundary accurately.
- Known risks are documented rather than hidden.
- Local runtime artifacts such as `.memisalluneed/`, `.worktrees/`, cache
  files, generated memories, and `.codex` are not committed.
- The repository is ready to tag as `v0.1.0`.

### Out of Scope

- Memory decay.
- New time-aware filtering behavior.
- Full plugin runtime.
- Large unrelated refactors.

## Phase 5.5: Memory Decay

### Status

Planned after `v0.1.0`.

### Goal

Introduce memory decay so recall can account for memory freshness, use,
confidence, and lifecycle without deleting old memories by default.

Decay should affect ranking, presentation, and archival hints. It should not
silently erase historical memory.

### Possible Signals

- memory age;
- `usage_count`;
- `last_recalled_at`;
- confidence;
- memory state such as uncertain, outdated, contradicted, or superseded;
- host feedback;
- manual pinning or protection metadata.

### Success Criteria

- Older or unused memories can lose priority without becoming unreachable.
- Pinned or frequently useful memories can resist decay.
- Decay behavior is explainable in recall traces.
- Decay does not destructively mutate or delete memories by default.

## Phase 5.6: Time-Aware Filtering

### Status

Planned after `v0.1.0`.

### Goal

Make recall and platform APIs more sensitive to explicit temporal constraints.

Phase 3.5 resolves timestamps after relevance recall. Phase 5.6 should add
time-aware filtering before or during candidate selection when the user or host
provides a time window or temporal intent.

### Possible Capabilities

- Recall memories within a host-provided time range.
- Prefer memories before or after a specified event.
- Support relative temporal requests such as recent, older, latest, or before a
  known project phase.
- Preserve temporal filter metadata in recall traces.
- Expose time filters through FastAPI platform requests.

### Success Criteria

- Hosts can provide explicit time filters in recall requests.
- Time filters affect candidate selection, not only final prompt ordering.
- Time-aware behavior is visible in recall traces.
- Time filtering works with BM25, semantic, and hybrid recall modes.

## Standing Boundary Rules

These rules apply across future phases unless a later approved spec explicitly
changes them:

- SQLite remains the canonical structured memory store.
- Do not add an `embedding` column to the SQLite `memories` table.
- Semantic vectors, if introduced, belong in a dedicated vector index or vector
  database.
- External knowledge is supplied by the host application.
- MEMisALLuNEED does not perform its own web search, crawling, or external
  acquisition loop.
- MEMisALLuNEED does not own memory sufficiency judgment for host answers.
- Old memories are not deleted or overwritten by default to resolve conflict.
- Conflict, uncertainty, outdatedness, and contradiction should be represented
  through state, metadata, provenance, and graph relations.
- Evaluation and observability should include failed, uncertain, outdated, and
  contradicted memories, not only successful memory paths.
