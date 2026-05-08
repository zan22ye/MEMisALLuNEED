# Local UI Console Design

## Goal

Build a local browser-based console for MEMisALLuNEED that helps a developer use
the system without repeatedly typing CLI commands.

The first version should provide:

- a memory management panel;
- a chat workbench;
- local-only operation through `127.0.0.1`;
- direct reuse of the existing Python memory, search, chat, session, and config
  code paths.

This is a local developer tool, not a hosted web product.

## Product Scope

The UI is launched from the CLI:

```bash
mem ui
```

It starts a local HTTP server and prints the local URL, for example:

```text
MEMisALLuNEED UI running at http://127.0.0.1:8765
```

Supported options:

```bash
mem ui --db .memisalluneed/memory.db
mem ui --config .memisalluneed/config.toml
mem ui --host 127.0.0.1
mem ui --port 8765
```

The default host must be:

```text
127.0.0.1
```

The UI must not bind to `0.0.0.0` by default.

## Non-Goals

The first version does not include:

- hosted deployment;
- user accounts;
- authentication;
- multi-user concurrency;
- WebSocket or streaming responses;
- markdown rendering beyond plain text display;
- memory editing or deletion;
- host integration UI;
- real-model smoke test UI;
- graph visualization;
- vector search;
- external web search;
- file/document ingestion.

## Architecture

Use a Python local web server plus static frontend assets.

Suggested files:

```text
memisalluneed/
  ui_server.py
  ui_static/
    index.html
    app.js
    styles.css
```

CLI integration:

```text
memisalluneed/cli.py
```

The server should use only the Python standard library for the first version,
preferably `http.server`, to avoid adding frontend or backend dependencies.

The frontend should be plain HTML, CSS, and JavaScript. Do not introduce
React, Vite, Node, or a build step in the first version.

## Backend Responsibilities

The local UI server should:

- serve static files from `memisalluneed/ui_static/`;
- expose JSON API endpoints;
- open and initialize the selected SQLite memory database;
- load the selected config path when chat APIs need models;
- preserve the existing `.memisalluneed/session.json` behavior for the selected
  config;
- return structured JSON errors instead of raw tracebacks;
- keep the API local-only by default.

The backend should reuse existing modules:

- `MemoryStore`;
- `search_memories`;
- `export_jsonl_text`;
- `create_memory_item`;
- `load_config`;
- `run_chat_once`;
- `flush_session_on_exit`;
- `_model_from_config`;
- `_session_path_for_config`.

If `_model_from_config` or `_session_path_for_config` remain private helpers in
`cli.py`, the implementation may either import them from `cli.py` for the first
version or extract public equivalents later. The first version should prefer the
smallest change that keeps behavior identical to `mem chat`.

## Frontend Structure

The UI should be a tool surface, not a landing page.

Top bar:

- product name: `MEMisALLuNEED`;
- current DB path;
- current config path;
- status indicator.

Primary navigation:

```text
Memories
Chat
```

Do not create decorative hero sections or marketing content.

## Memories Tab

The Memories tab should support:

- listing recent memories;
- searching memories;
- adding a new memory;
- filtering by memory type;
- filtering by memory state;
- viewing full memory details;
- exporting JSONL.

### Memory List

Each memory row/card should show:

- id preview;
- type;
- state;
- confidence;
- created_at;
- usage_count;
- last_recalled_at when present;
- content preview.

Clicking a memory opens a detail panel.

### Memory Detail

The detail panel should show:

- full id;
- type;
- state;
- confidence;
- content;
- metadata as formatted JSON;
- created_at;
- updated_at;
- usage_count;
- last_recalled_at.

### Add Memory

The add form should include:

- content textarea;
- type select with `knowledge`, `experience`, `recall`, `source`;
- state select with `success`, `failed`, `uncertain`, `contradicted`,
  `outdated`;
- confidence numeric input from `0.0` to `1.0`;
- metadata JSON textarea.

On submit:

- validate that content is non-empty;
- validate that metadata parses as a JSON object;
- call the backend add endpoint;
- refresh the memory list on success;
- show a clear error message on failure.

### Search

Search should call the same keyword/token-overlap recall behavior as
`mem search`.

Search results should show:

- score;
- memory type;
- state;
- confidence;
- content preview.

Search may update `usage_count` and `last_recalled_at`, matching the existing
CLI search behavior.

### Export

Export should provide a button that downloads or displays JSONL from the current
database.

The first version may use a simple link/button that opens:

```text
GET /api/export
```

## Chat Tab

The Chat tab should support a non-streaming local chat workflow.

It should include:

- conversation panel;
- user input textarea;
- send button;
- used memories panel;
- new session button;
- flush session button;
- clear session button.

The first version should not require users to type `/exit` in the browser.

### Send Message

When the user sends a message, the frontend calls:

```text
POST /api/chat/send
```

The backend should:

1. load config;
2. construct chat and formation models from config;
3. call `run_chat_once`;
4. return assistant reply and used memory trace.

The response should include:

```json
{
  "assistant_reply": "...",
  "used_memories": [
    {
      "id": "...",
      "type": "knowledge",
      "state": "success",
      "confidence": 1.0,
      "content": "..."
    }
  ]
}
```

The frontend should append both the user message and assistant reply to the
conversation panel.

### Used Memories

The used memories panel should show:

- memory id preview;
- type;
- state;
- confidence;
- content preview.

If no memories are used, show a compact empty state.

### Session Controls

New Session:

- clears the active session file;
- starts subsequent messages from a fresh session.

Flush Session:

- calls `flush_session_on_exit`;
- writes remaining active turns into memory;
- clears the session file;
- refreshes memory list.

Clear Session:

- deletes the active session file without forming memories;
- matches the existing `mem chat --clear-session` behavior.

The UI should label these actions clearly because Flush Session and Clear
Session have different memory consequences.

## API Endpoints

Suggested API shape:

```text
GET  /api/status
GET  /api/memories?limit=50&type=&state=
POST /api/memories
GET  /api/memories/<id>
GET  /api/search?q=...&top_k=5
GET  /api/export
POST /api/chat/send
POST /api/chat/new-session
POST /api/chat/flush
POST /api/chat/clear
```

### `GET /api/status`

Returns:

```json
{
  "db_path": "...",
  "config_path": "...",
  "db_exists": true,
  "config_exists": true
}
```

It should not expose API key values.

### `GET /api/memories`

Returns recent memories from `MemoryStore.list(limit)`, optionally filtered by
type and state in the server layer.

### `POST /api/memories`

Request:

```json
{
  "content": "...",
  "type": "knowledge",
  "state": "success",
  "confidence": 1.0,
  "metadata": {}
}
```

Response:

```json
{
  "memory": {
    "id": "...",
    "type": "knowledge",
    "content": "..."
  }
}
```

### `GET /api/search`

Uses existing `search_memories`.

### `GET /api/export`

Returns JSONL with content type:

```text
application/x-ndjson; charset=utf-8
```

### `POST /api/chat/send`

Request:

```json
{
  "message": "..."
}
```

Response includes assistant reply and used memories.

### Error Shape

All JSON API errors should use:

```json
{
  "error": {
    "message": "...",
    "type": "..."
  }
}
```

Examples:

- missing config;
- invalid metadata JSON;
- missing API key environment variable;
- model provider request failure;
- unknown memory id;
- unsupported route.

## UI Behavior And Style

The UI should feel like a local operational tool:

- dense but readable;
- restrained colors;
- clear tables/lists;
- no marketing hero;
- no decorative background effects;
- no nested cards.

Use stable dimensions for:

- top bar;
- tab controls;
- memory list rows;
- chat input area;
- used memories panel.

The page should be responsive enough for a laptop browser and a narrow mobile
viewport, but desktop developer use is the primary target.

## Security And Locality

The server is a local developer tool.

Requirements:

- default bind host is `127.0.0.1`;
- do not expose API keys through `/api/status` or frontend state;
- do not log API key values;
- do not provide a remote deployment path in the first version.

If the user explicitly passes `--host 0.0.0.0`, the CLI may allow it, but the
default should stay local.

## Testing

Backend tests should cover:

- parser accepts `mem ui` options;
- status endpoint returns selected DB/config paths without secrets;
- list memories endpoint returns stored memories;
- add memory endpoint validates content and metadata;
- search endpoint returns scored memories;
- export endpoint returns parseable JSONL;
- chat send endpoint calls `run_chat_once` with fake models;
- flush endpoint calls `flush_session_on_exit`;
- clear endpoint deletes active session file.

Frontend tests can be lightweight in the first version:

- serve static `index.html`;
- verify that static assets are reachable;
- rely on manual browser verification for layout.

Manual verification should include:

- start `mem ui`;
- open the printed local URL;
- add a memory;
- search for that memory;
- inspect memory detail;
- export JSONL;
- send a chat message with fake or configured real model;
- inspect used memories;
- flush session.

## First-Version Acceptance Criteria

The feature is acceptable when:

- `mem ui --help` shows UI options;
- `mem ui` starts a local server on `127.0.0.1`;
- browser can load the UI;
- Memories tab can list, add, search, inspect, and export memories;
- Chat tab can send a message and display reply plus used memories;
- New Session, Flush Session, and Clear Session controls work;
- config/API key/model errors appear as readable UI errors;
- no Node/Vite/React build step is required;
- normal pytest suite passes.

## Future Work

Future versions may add:

- memory editing and deletion;
- host integration UI;
- real-model smoke benchmark controls;
- graph visualization;
- streaming chat responses;
- markdown rendering;
- import JSONL;
- richer filtering and sorting;
- theme customization.
