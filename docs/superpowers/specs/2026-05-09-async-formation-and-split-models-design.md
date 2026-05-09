# Async Formation and Split Models Design

Date: 2026-05-09

## Purpose

The local UI currently needs a cleaner separation between answering and memory
formation. Chat should stay responsive even when memory formation is slow, and
the formation model should be independently configurable so users can choose a
faster or cheaper model for memory extraction.

This design covers two changes:

- asynchronous formation for turns rolled out of the active session window;
- independent chat and formation model configuration using the existing
  `[chat_model]` and `[formation_model]` sections.

## Non-Goals

- Do not restore per-turn automatic memory formation in UI chat.
- Do not add embeddings or vector search.
- Do not add a new `formation_turns` setting.
- Do not choose a new default SiliconFlow formation model name in code.
- Do not migrate formation job state into the long-term memory table.

## Current Behavior

`mem chat` and the local UI use `run_chat_once` to:

1. load active session state;
2. recall existing memories;
3. call the chat model;
4. append the new turn to active session;
5. roll old turns if `max_turns` or `max_tokens` is exceeded;
6. synchronously form memories for rolled turns.

The local UI no longer forms memory after every chat turn. `Flush Session`
still synchronously forms all active, unwritten turns.

## Target Behavior

### Chat Send

For a normal UI chat message:

1. the server recalls memories;
2. the server calls only the chat model on the request path;
3. the new turn is saved to active session;
4. if the active session exceeds `max_turns` or `max_tokens`, rolled turns are
   removed from active session and enqueued as background formation jobs;
5. the HTTP response returns as soon as the chat reply and enqueue step finish.

Chat send must not wait for the formation model.

If no turns roll out of the active session, no formation jobs are created.

### Flush Session

`Flush Session` remains a manual, synchronous operation:

1. the user clicks the UI button;
2. active session turns are formed immediately using the configured formation
   model;
3. successfully written memories are returned in the response;
4. active session is cleared after successful flush.

This is intentionally different from background rolling formation because the
button means "write this now."

### Background Formation Jobs

When turns roll out of active session, each rolled turn becomes a local
formation job. Jobs have these statuses:

- `pending`;
- `running`;
- `written`;
- `failed`.

Failed jobs remain failed and do not put the turn back into active session.
Users can retry failed jobs from the UI.

## Job Storage

Store formation job state in a local JSON file next to the active session:

```text
.memisalluneed/formation_jobs.json
```

This file is local runtime state, not long-term memory. It should remain ignored
by git through the existing `.memisalluneed/` ignore rule.

Each job should include:

```json
{
  "id": "formation-job-id",
  "session_id": "session-id",
  "turn": {
    "id": "turn-id",
    "user_message": "...",
    "assistant_message": "...",
    "recalled_memory_ids": [],
    "created_at": "..."
  },
  "status": "pending",
  "written_memory_ids": [],
  "error": null,
  "created_at": "...",
  "updated_at": "..."
}
```

The job store should expose small operations:

- append jobs;
- list recent jobs;
- mark running;
- mark written with memory ids;
- mark failed with an error message;
- reset a failed job to pending for retry.

## Background Worker

Use the Python standard library:

```text
queue.Queue + worker thread
```

When the UI server starts, it starts one worker thread. The worker:

1. reads pending jobs from the in-memory queue;
2. marks a job `running`;
3. hydrates recalled memories from the store;
4. calls `FormationService.form_from_chat_qa_turn`;
5. records written memory ids and marks the job `written`;
6. records error text and marks the job `failed` on exception.

At startup, existing `pending` jobs from the JSON file should be enqueued again.
Existing `running` jobs should be treated as interrupted and reset to `pending`
before enqueueing.

## API

Add UI APIs:

```text
GET  /api/formation/jobs
POST /api/formation/jobs/<id>/retry
```

`GET /api/formation/jobs` returns recent jobs sorted newest first:

```json
{
  "jobs": [
    {
      "id": "...",
      "turn_id": "...",
      "status": "failed",
      "written_memory_ids": [],
      "error": "The read operation timed out",
      "created_at": "...",
      "updated_at": "..."
    }
  ]
}
```

`POST /api/formation/jobs/<id>/retry` only accepts failed jobs. It clears the
error, marks the job pending, and enqueues it.

`POST /api/chat/send` should include jobs created by that request:

```json
{
  "assistant_reply": "...",
  "used_memories": [],
  "written_memories": [],
  "formation_jobs": []
}
```

`written_memories` remains an empty list for normal chat send. It is kept for
response-shape compatibility.

## UI

The local UI should show a compact formation job panel in the Chat tab.

The panel should show:

- latest job status;
- pending/running/written/failed counts;
- recent jobs with `turn_id`, status, written count, and error text;
- retry action for failed jobs.

The UI should poll `GET /api/formation/jobs` periodically while the Chat tab is
open, and after every chat send.

## Model Configuration

Keep the current config shape:

```toml
[chat_model]
provider = "siliconflow"
model = "Pro/zai-org/GLM-4.7"

[formation_model]
provider = "siliconflow"
model = "Pro/zai-org/GLM-4.7"
```

The two sections already allow independent providers and model names. The spec
does not choose a new default formation model. Documentation and example text
should state that `formation_model` can be changed to a faster and cheaper
model without changing the chat model.

The UI status endpoint should continue reporting both chat and formation model
readiness separately.

## Error Handling

- Chat model failure: the chat request fails and the UI shows the error.
- Enqueue failure: the chat request fails because the rolled turn could not be
  safely persisted for formation.
- Background formation failure: the chat request is not affected; the job is
  marked `failed` with an error message.
- Retry failure: the job remains `failed` with updated error text.
- Worker restart: `running` jobs from the previous process are reset to
  `pending` and retried.

## Testing

Tests should cover:

- normal chat send does not call the formation model when no turn rolls;
- chat send returns before a queued formation job is processed;
- exceeding `max_turns` creates a pending formation job;
- the worker writes memories and marks the job `written`;
- worker failure marks the job `failed` and preserves the error;
- retrying a failed job re-enqueues it;
- `Flush Session` still synchronously writes active session memories;
- chat and formation models can be configured independently;
- UI/API job responses have stable JSON shapes.

## Acceptance Criteria

- Normal UI chat waits only for chat generation and enqueue work.
- Rolled turns become background formation jobs.
- Failed background jobs are visible and retryable.
- Manual `Flush Session` still immediately writes active session turns.
- The formation model remains independently configurable.
- The full test suite passes.
