# Chat Observability Workbench Design

Date: 2026-05-11

## Goal

Improve the local MEMisALLuNEED UI into a practical chat observability
workbench.

The first productization pass should make memory-centric chat easier to use and
debug by showing, per assistant turn:

- the conversation in a large primary workspace;
- the memories used by the answer;
- recall scores and memory metadata summaries;
- formation job status for rolled turns;
- enough session and runtime state to diagnose local behavior.

This is still a local developer tool launched by `mem ui`, not a hosted product.

## User Direction

The selected direction is:

```text
Conversation-large three-pane workbench with collapsible side panels.
```

The conversation pane must be visually dominant. Side panels exist to support
inspection, not to compete with the chat transcript.

## Current Behavior

The local UI currently has two top-level tabs:

- `Memories`;
- `Chat`.

The Chat tab supports:

- sending a non-streaming message;
- showing the assistant reply;
- showing used memories as raw JSON;
- creating background formation jobs for rolled turns;
- polling recent formation jobs;
- new session, flush session, and clear session actions.

The backend already exposes:

- `POST /api/chat/send`;
- `POST /api/chat/new-session`;
- `POST /api/chat/flush`;
- `POST /api/chat/clear`;
- `GET /api/formation/jobs`;
- `POST /api/formation/jobs/<id>/retry`.

The backend response for `POST /api/chat/send` includes `assistant_reply`,
`used_memories`, `written_memories`, and `formation_jobs`, but the frontend does
not organize this by selected turn or present it as an inspector workflow.

## Non-Goals

This MVP does not include:

- graph visualization;
- vector search;
- streaming chat responses;
- a React, Vite, Node, or frontend build step;
- hosted deployment or authentication;
- full event timeline visualization;
- memory editing or deletion;
- host integration UI;
- a new trace database;
- new long-term storage tables;
- memory graph reasoning;
- automatic contradiction detection.

## UX Design

### Layout

Use a three-pane layout in the Chat workspace:

```text
left session summary | large conversation pane | collapsible trace inspector
```

The default desktop layout should keep the conversation pane largest:

- left panel: narrow and persistent;
- center panel: large transcript and large multi-line input;
- right panel: visible by default but collapsible to a narrow rail.

When the right panel is collapsed, the conversation pane expands into the freed
space. On narrow viewports, side panels should behave like drawers or stacked
sections so the chat transcript remains readable.

### Left Session Summary

The left panel should show compact operational state:

- active turn count;
- approximate active session token count when available;
- configured `max_turns` and `max_tokens`;
- formation job counts by status;
- session actions: new session, flush session, clear session.

The panel should not show full memory content. It is a status and control area.

### Conversation Pane

The center pane is the primary workspace. It should show:

- user and assistant turns as readable transcript entries;
- selected-turn affordance for assistant turns;
- a large multi-line message input;
- a clear send action;
- loading and error states near the input.

After a message is sent, the new assistant turn should become the selected turn
so the right inspector immediately describes what happened.

### Trace Inspector

The right panel shows trace information for the selected assistant turn.

It should show:

- selected turn id or short id;
- user message preview;
- assistant reply preview;
- used memories as compact memory preview cards;
- formation jobs created by that turn, if any;
- written memory ids for completed jobs when available;
- an empty state when no turn is selected;
- an unavailable state for data that cannot be derived from current storage.

The inspector must be collapsible. Collapsing it should preserve selected-turn
state so reopening it returns to the same turn trace.

### Memory Preview Cards

Each used memory should render as a compact card with:

- memory id preview;
- type;
- state;
- confidence;
- recall score when available;
- usage count;
- content preview;
- created timestamp.

Clicking a card may open the existing full memory detail behavior if available.
The MVP does not need inline memory editing.

## Backend Design

### Keep Existing Core Paths

The workbench should reuse current backend behavior:

- `run_chat_once`;
- BM25 recall through `search_memories`;
- timestamp-aware resolution inside chat prompt construction;
- session JSON through `SessionState`;
- background formation jobs through `FormationJobStore`;
- memory access through `MemoryStore`.

The UI must not fork chat behavior from CLI behavior.

### Add Session Endpoint

Add:

```text
GET /api/chat/session
```

Response:

```json
{
  "session": {
    "session_id": "...",
    "created_at": "...",
    "updated_at": "...",
    "turns": [
      {
        "id": "...",
        "user_message": "...",
        "assistant_message": "...",
        "recalled_memory_ids": [],
        "created_at": "..."
      }
    ]
  },
  "summary": {
    "active_turn_count": 1,
    "max_turns": 6,
    "max_tokens": 100000,
    "estimated_tokens": 1234
  }
}
```

`estimated_tokens` may use the existing lightweight session token estimate. If
that estimate is not exposed cleanly yet, the field may be `null` in the first
implementation.

### Extend Chat Send Response

`POST /api/chat/send` should continue returning the existing response fields and
add the new turn id:

```json
{
  "turn_id": "...",
  "assistant_reply": "...",
  "used_memories": [],
  "written_memories": [],
  "formation_jobs": []
}
```

If returning the turn id requires a small change to `run_chat_once` or the UI
wrapper, keep that change focused and covered by tests.

### Add Trace Endpoint

Add:

```text
GET /api/chat/trace?turn_id=<turn-id>
```

Response:

```json
{
  "turn": {
    "id": "...",
    "user_message": "...",
    "assistant_message": "...",
    "created_at": "..."
  },
  "used_memories": [
    {
      "score": 1.23,
      "memory": {}
    }
  ],
  "formation_jobs": [],
  "unavailable": []
}
```

The endpoint should derive trace data from existing sources:

- current active session turns;
- recent formation jobs;
- `recalled_memory_ids` on the session turn;
- memory records in SQLite.

If a score is unavailable for a historical turn, return `score: null` and add a
short marker to `unavailable`, for example:

```json
"unavailable": ["recall_scores"]
```

Do not create a new persistent trace store in this MVP.

## Frontend Design

Keep the frontend as plain HTML, CSS, and JavaScript.

Suggested component-level organization inside `app.js`:

- layout state for selected tab, selected turn id, and right-panel collapsed
  state;
- `renderConversation(session, selectedTurnId)`;
- `renderTrace(trace)`;
- `renderSessionSummary(session, jobs, status)`;
- `renderMemoryPreviewCard(entry)`;
- `loadChatSession()`;
- `loadTurnTrace(turnId)`.

The implementation can remain in one file for this MVP, but it should avoid
large inline HTML strings where small helper render functions make behavior
clearer.

## Error Handling

The UI should use existing structured API errors.

Expected frontend states:

- config missing or invalid: show status in the top bar and disable send;
- missing API key: show model readiness and explain which env var is missing;
- chat send error: show near input without clearing the draft message;
- trace load error: show in the trace inspector without breaking chat;
- formation job failure: show failed status and retry action.

## Testing

Add focused tests for backend helpers and route behavior:

- `GET /api/chat/session` returns active session turns and summary fields.
- `POST /api/chat/send` returns the new `turn_id`.
- `GET /api/chat/trace` returns the selected turn, hydrated memories, and jobs.
- trace returns `score: null` and an `unavailable` marker when score data cannot
  be reconstructed.
- empty or missing turn id returns a structured bad request or not found error.

Add frontend-oriented tests at the level already used by the project. If no DOM
test harness exists, keep frontend validation to focused static and helper
function coverage where practical, and rely on API tests for data contracts.

## Acceptance Criteria

- The Chat tab uses a conversation-large layout.
- The right trace inspector can collapse and expand.
- Sending a message appends a user/assistant turn and selects the new assistant
  turn.
- The selected turn shows used memory preview cards instead of raw JSON.
- The selected turn shows related formation jobs when jobs exist.
- Existing memory management behavior remains available.
- Existing `mem chat` CLI behavior is unchanged.
- Existing UI formation job polling and retry behavior still works.
- Full non-real-model test suite passes.
