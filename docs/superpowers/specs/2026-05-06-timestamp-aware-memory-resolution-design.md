# Timestamp-Aware Memory Resolution Design

## Goal

Introduce a timestamp-aware resolver layer so MEMisALLuNEED can keep all
memories without deleting or overwriting older ones, while still preferring
newer relevant memories when constructing the primary QA context.

This design follows the project thesis that everything before the current
moment can be treated as memory. A contradicted or outdated memory is still
memory; it should remain inspectable as historical context.

## Core Rule

The system must not delete memories to resolve conflict.

When multiple relevant memories are available, `created_at` is used after
relevance recall to decide which memories should be treated as primary context
and which should be treated as older relevant context for the current query.

## Non-Goals

This phase does not add:

- recency-only candidate retrieval;
- external search;
- semantic embeddings;
- vector database integration;
- graph reasoning;
- automatic contradiction detection;
- automatic mutation of old memory state;
- deletion or overwrite of old memories.

## Candidate Selection

Timestamp-aware resolution must not add a recency-only candidate channel.

Candidate memories are selected only through relevance recall. Recency is used
only after relevance candidates have already been selected.

The recall flow should use a larger candidate pool than the final context:

```text
query
  -> relevance recall with candidate_k
  -> timestamp-aware resolver
  -> final context with final_k or token budget
```

Example defaults:

```text
candidate_k = 50
final_k = existing recall_top_k
```

This handles cases where a newer relevant memory would not have reached the
old final top-k. It does not handle memories that cannot be found by the
current relevance search at all. That limitation belongs to the search layer
and can be addressed later through semantic recall, subject indexes, or memory
graph relations.

## Resolver Model

Add a resolver module:

```text
memisalluneed/resolution.py
```

It should expose:

```python
@dataclass(frozen=True)
class ResolvedMemoryContext:
    primary: list[MemorySearchResult]
    older_relevant: list[MemorySearchResult]
    unresolved_time: list[MemorySearchResult]


def resolve_current_memories(
    results: list[MemorySearchResult],
    *,
    final_k: int,
) -> ResolvedMemoryContext:
    ...
```

Initial resolver behavior should be conservative:

1. It receives relevance-ranked `MemorySearchResult` candidates.
2. It parses `item.created_at`.
3. Candidates with invalid timestamps go to `unresolved_time`.
4. Valid candidates are sorted newest first.
5. The newest valid candidates up to `final_k` go to `primary`.
6. Remaining valid candidates go to `older_relevant`.
7. It does not mutate `MemoryStore`.
8. It does not delete or change memory items.

This initial design intentionally does not attempt subject grouping. Without a
memory graph or entity resolver, grouping by subject would be fragile. Phase 5
can later refine this by using `updates`, `supersedes`, and `contradicts`
relations.

## Chat Context

`mem chat` should use a broad candidate recall:

```text
candidate_k = max(config.session.recall_top_k, configured candidate_k)
```

Then it should resolve candidates before constructing the chat prompt.

The prompt should distinguish:

- primary memories;
- older relevant memories;
- timestamp-unresolved memories.

The chat system instruction should explain:

- newer relevant memories should be treated as more current when memories
  conflict;
- older relevant memories are still relevant context, but may be less current;
- older relevant memories should not be deleted or ignored, but should not be
  presented as current facts when a newer relevant memory conflicts with them;
- timestamp-unresolved memories have timestamp issues and should be used
  cautiously.

## Used Memory IDs

Phase 3 defines `used_memory_ids = recalled_memory_ids`.

With timestamp-aware resolution, the stored turn should continue recording all
candidate memory ids that are supplied to the chat prompt. The resolver does
not silently drop historical context from trace metadata.

If a final token budget requires pruning, the pruned memories should not be
recorded as used because they were not supplied to the answer context.

## CLI and Config

Do not change `mem search` behavior in this phase.

Add session config for broad recall only if needed:

```toml
[session]
recall_candidate_k = 50
recall_top_k = 5
```

If config migration would add too much scope, Phase 3.5 may derive
`candidate_k` from `recall_top_k`, for example:

```python
candidate_k = max(config.session.recall_top_k, 50)
```

The preferred implementation is an explicit `recall_candidate_k` config value
because it makes the broad candidate pool visible and testable.

## Tests

Tests should verify:

- newer valid candidates become `primary`;
- older valid candidates remain `older_relevant`;
- invalid timestamps become `unresolved_time`;
- resolver does not mutate memory items or delete stored memory;
- `mem chat` calls search with `recall_candidate_k`, not final `recall_top_k`;
- chat prompt includes primary, older relevant, and timestamp-unresolved
  sections;
- no recent-only candidate retrieval exists;
- `mem search` remains unchanged.

## Roadmap Placement

This should be treated as Phase 3.5: Timestamp-Aware Memory Resolution.

It belongs after Phase 3 because Phase 3 already creates QA recall traces, and
before Phase 4 because it improves memory-only answering without adding
external acquisition.
