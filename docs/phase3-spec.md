# Phase 3 Spec: Memory-Centric QA in `mem chat`

Phase 3 strengthens `mem chat` as the unified question-answering interface.

The key change is that chat turns become explicitly QA-aware when they are
formed into memory. Each turn records which memories were recalled, which
memories were treated as used, and how the interaction should become reusable
experience.

Phase 3 does not introduce a separate one-shot QA command.

## Goal

Build memory-centric QA behavior inside `mem chat` so that:

1. each chat response is generated with recalled memory;
2. users can optionally inspect which memories were used;
3. session content is still written to memory only when it leaves active
   context;
4. each formed QA turn preserves recall trace metadata;
5. QA experience becomes reusable memory.

Phase 3 should prove:

> `mem chat` can answer through a bounded active session plus recalled memory,
> and can later form each completed QA turn into structured memory.

## Non-Goals

Phase 3 should not implement:

- a separate one-shot QA command;
- a separate ask model or answer model;
- a memory sufficiency judge;
- external search;
- search-judge external acquisition loop;
- document ingestion;
- vector database integration;
- embedding columns in SQLite;
- memory graph reasoning;
- conflict detection;
- benchmark evaluation;
- immediate memory writing after every assistant response.

## Core Flow

`mem chat` remains the only user-facing QA entry point.

For each user message:

1. recall relevant memory items;
2. call the chat model with the bounded active session, recalled memories, and
   current user message;
3. store the completed turn in the active session with recalled memory ids;
4. when the turn rolls out of the active session, form that turn into memory;
5. when chat exits, flush remaining active turns one by one into memory.

Phase 3 keeps the Phase 2 memory formation timing:

- memory is written when a turn rolls out of the active session;
- memory is written when chat exits and remaining active turns are flushed.

Phase 3 does not add per-turn immediate memory writes after every answer.

## User-Facing CLI

`mem chat` remains the command:

```bash
mem chat
```

Phase 3 adds an optional trace display flag:

```bash
mem chat --show-memory-trace
```

By default, chat responses should remain clean and should not print recall
trace details.

When `--show-memory-trace` is enabled, each assistant reply should be followed
by a compact memory trace:

```text
Used memories:
- <id> <type> <state> confidence=<confidence>
```

If no memories were recalled, the trace should make that clear without writing
extra memory by itself:

```text
Used memories:
- none
```

Phase 3 treats all recalled memories as used memories:

```text
used_memory_ids = recalled_memory_ids
```

Phase 3 does not display or persist retrieval scores.

## Formation Timing

Formation still happens only when active session content leaves the active
context.

### Rolling Formation

When a turn is rolled out because the active session exceeds `max_turns` or
`max_tokens`, that single turn should be formed into memory.

### Exit Flush Formation

When chat exits, remaining active turns should be formed one turn at a time.

Exit flush should not send the whole remaining active session as one combined
formation batch in Phase 3.

The Phase 3 granularity is:

```text
one chat turn -> one chat_qa payload -> memory candidates
```

## Formation Payload

Phase 3 introduces a `chat_qa` formation kind.

Each rolled or flushed turn should be passed to the formation model with a
payload shaped like this:

```json
{
  "formation_kind": "chat_qa",
  "session_id": "...",
  "turn": {
    "id": "...",
    "user_message": "...",
    "assistant_message": "...",
    "created_at": "..."
  },
  "recalled_memories": [
    {
      "id": "...",
      "type": "knowledge",
      "state": "success",
      "confidence": 1.0,
      "content": "..."
    }
  ],
  "used_memory_ids": ["..."]
}
```

The payload should not include `score` or `recall_scores`.

`confidence` is included because it is an existing memory field. It describes
the reliability of the memory itself, not the retrieval relevance for the
current query.

## Formation Output Contract

For each `chat_qa` turn, the formation model should return memory candidates in
the existing format:

```json
{
  "memories": [
    {
      "type": "experience",
      "content": "...",
      "state": "success",
      "confidence": 0.9,
      "metadata": {
        "source": "chat_session",
        "formation_kind": "chat_qa",
        "session_id": "...",
        "turn_id": "...",
        "recalled_memory_ids": ["..."],
        "used_memory_ids": ["..."]
      }
    }
  ]
}
```

For each `chat_qa` turn, the expected output is:

- at least one `experience` memory;
- zero or more `recall` memories;
- zero or more `knowledge` memories;
- no `source` memories in Phase 3.

`experience` memory is required because each completed QA turn is reusable
experience.

`recall` memory is optional. If the turn did not recall memory, or if the recall
event is not useful enough to preserve as a separate memory item, the formation
model does not need to emit a `recall` memory.

`knowledge` memory is optional. It should be emitted only when the turn produced
a reusable conclusion, decision, fact, or method.

`source` memory is out of scope because Phase 3 does not acquire external
sources.

Invalid memory candidates should continue to be discarded by the existing
validation path.

## Required Metadata

Every `chat_qa` `experience` memory must include:

```json
{
  "source": "chat_session",
  "formation_kind": "chat_qa",
  "session_id": "...",
  "turn_id": "...",
  "recalled_memory_ids": ["..."],
  "used_memory_ids": ["..."]
}
```

If the formation model emits a `recall` memory for the same turn, that memory
should include the same trace fields.

Recall trace metadata must be preserved in the `experience` memory even when no
separate `recall` memory is emitted.

## Metadata Updates

Recalled memories should continue to update:

- `usage_count`;
- `last_recalled_at`.

This metadata update should happen during recall, as in the existing search
path.

Phase 3 does not introduce dedicated answer-to-memory tables or graph edges.
The used-memory relationship is recorded in memory metadata through
`used_memory_ids`.

## Success Criteria

Phase 3 is complete when:

- `mem chat` remains the unified QA interface;
- no separate one-shot QA command exists;
- every chat response can use recalled memories;
- `--show-memory-trace` displays used memory ids, types, states, and confidence
  values;
- used memories are treated as all recalled memories in Phase 3;
- retrieval scores are not displayed, stored in the session, or written to
  memory metadata;
- recalled memories update `usage_count` and `last_recalled_at`;
- rolling formation processes one rolled turn at a time;
- exit flush processes remaining active turns one turn at a time;
- each turn uses `formation_kind = "chat_qa"` when formed into memory;
- each formed `chat_qa` turn produces at least one `experience` memory;
- `experience` memory metadata includes `session_id`, `turn_id`,
  `recalled_memory_ids`, and `used_memory_ids`;
- `recall` and `knowledge` memories can be emitted when useful;
- Phase 3 does not write `source` memories;
- Phase 3 does not perform immediate memory formation after every assistant
  response.
