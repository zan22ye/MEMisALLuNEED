# Phase 2 Spec: Session to Memory Formation

Phase 2 upgrades MEMisALLuNEED from a manual memory substrate into a chat session that automatically forms memory.

The key change is that `mem chat` uses two distinct model roles:

- a **chat model** for assistant replies;
- a **formation model** for cleaning, compressing, structuring, and writing memories.

Both model roles are configurable and can use GPT, Kimi, or Qwen through OpenAI-compatible APIs.

## Goal

Build an interactive `mem chat` mode that:

1. loads configuration from local runtime config;
2. recalls relevant memories before each assistant reply;
3. calls a chat model to generate the assistant reply;
4. stores each chat turn in a bounded active session window;
5. rolls old turns out of the active window when limits are exceeded;
6. calls a formation model to turn rolled or flushed session content into memory items;
7. writes validated memory items into the existing SQLite memory store.

Phase 2 should prove:

> A bounded session can use memory during chat and automatically form new memories through a dedicated formation model.

## Non-Goals

Phase 2 should not implement:

- a separate one-shot QA command;
- external knowledge acquisition;
- web search;
- document ingestion;
- vector database integration;
- embedding columns in SQLite;
- memory graph reasoning;
- conflict detection;
- outdated-memory detection;
- benchmark evaluation.

## Configuration Strategy

Phase 2 uses both versioned example config and local runtime config.

### Versioned Example Config

The repository should include:

- `config.example.toml`

This file documents how to configure:

- chat model;
- formation model;
- GPT provider;
- Kimi provider;
- Qwen provider;
- session window limits;
- request timeout.

It must not contain real API keys.

### Local Runtime Config

The default runtime config path is:

- `.memisalluneed/config.toml`

This file is not committed because `.memisalluneed/` is ignored.

`mem chat` should load `.memisalluneed/config.toml` by default.

Users can override the config path with:

```bash
mem chat --config path/to/config.toml
```

### Example Config

```toml
[chat_model]
provider = "openai"
model = "gpt-4.1"

[formation_model]
provider = "openai"
model = "gpt-4.1-mini"

[session]
max_turns = 6
max_tokens = 100000
recall_top_k = 5

[http]
request_timeout = 60

[providers.openai]
api_key_env = "OPENAI_API_KEY"
base_url = "https://api.openai.com/v1"

[providers.kimi]
api_key_env = "KIMI_API_KEY"
base_url = "https://api.moonshot.cn/v1"

[providers.qwen]
api_key_env = "QWEN_API_KEY"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
```

### CLI Overrides

`mem chat` should support these config overrides:

```bash
mem chat --config path/to/config.toml
mem chat --chat-provider openai
mem chat --chat-model gpt-4.1
mem chat --formation-provider qwen
mem chat --formation-model qwen-turbo
mem chat --max-turns 6
mem chat --max-tokens 100000
mem chat --recall-top-k 5
```

## Model Roles

Phase 2 must keep chat and formation roles separate.

### Chat Model

The chat model is responsible for producing assistant replies in `mem chat`.

Input:

- active session window;
- recalled memories;
- current user message.

Output:

- assistant message text.

The chat model does not write memory directly.

### Formation Model

The formation model is responsible for producing structured memory candidates.

Input:

- rolled turn, or remaining active window on exit;
- recalled memory ids and optionally recalled memory contents;
- formation kind.

Output:

- JSON object containing memory candidates.

The formation model does not talk to the user.

## Provider Support

Phase 2 must support at least:

- GPT;
- Kimi;
- Qwen.

These should be implemented through a shared OpenAI-compatible adapter where possible.

Provider differences should live in configuration:

- `provider`;
- `model`;
- `base_url`;
- `api_key_env`;
- `request_timeout`.

The formation and chat models can use:

- the same provider with different models;
- different providers;
- different base URLs;
- different API key environment variables.

## HTTP Client

Phase 2 should use:

- `httpx`

Add dependency:

```toml
dependencies = [
  "httpx>=0.27",
]
```

The model adapter should call:

```text
POST {base_url}/chat/completions
```

Tests must not require real network access or real API keys. Use fake clients or mock transports.

## Suggested Modules

```text
memisalluneed/
  config.py
  session.py
  formation.py
  models/
    __init__.py
    base.py
    openai_compatible.py
```

### `config.py`

Responsibilities:

- load TOML config;
- validate required config fields;
- apply CLI overrides;
- expose typed config objects.

Use Python standard library `tomllib` for reading TOML.

### `session.py`

Responsibilities:

- represent `SessionTurn`;
- manage active session window;
- persist `.memisalluneed/session.json`;
- load existing active window;
- clear session on normal exit;
- roll old turns when limits are exceeded.

### `formation.py`

Responsibilities:

- build formation prompts;
- call formation model;
- parse formation JSON;
- validate memory candidates;
- convert valid candidates into `MemoryItem`s;
- write valid memories to `MemoryStore`.

### `models/base.py`

Responsibilities:

- define provider-independent model client interface;
- define model request/response types if needed.

### `models/openai_compatible.py`

Responsibilities:

- implement OpenAI-compatible chat completions request;
- read API key from configured environment variable;
- apply timeout;
- parse assistant content from provider response;
- raise clear errors for missing API keys and malformed responses.

## `mem chat` CLI Contract

Add command:

```bash
mem chat
```

Options:

- `--config <path>`: config path, default `.memisalluneed/config.toml`;
- `--db <path>`: memory DB path, default `.memisalluneed/memory.db`;
- `--chat-provider <name>`;
- `--chat-model <name>`;
- `--formation-provider <name>`;
- `--formation-model <name>`;
- `--max-turns <n>`;
- `--max-tokens <n>`;
- `--recall-top-k <n>`;
- `--new-session`: ignore existing active session and start a new one;
- `--clear-session`: delete current active session and exit;
- `--no-resume`: do not load existing active session for this run.

Commands inside chat:

- `/exit`: flush active window to memory and exit;
- `/quit`: same as `/exit`;
- Ctrl-D: same as `/exit` when possible.

## Session Window Rule

Phase 2 uses both turn and token limits.

Defaults:

```toml
[session]
max_turns = 6
max_tokens = 100000
```

Rolling rule:

```text
while active_turns > max_turns OR active_tokens > max_tokens:
    remove oldest turn
    send that turn to formation model
    validate generated memories
    write valid memories to SQLite
```

Whichever limit is exceeded first triggers rolling.

`max_turns = 6` should usually trigger first in early development. `max_tokens = 100000` is a safety limit for very large inputs.

Token counting can be approximate in Phase 2. A simple character-based approximation is acceptable as long as the implementation is deterministic and documented.

## Session Persistence

Phase 2 does not persist the full raw session log.

It persists only the current active window.

Default session file:

- `.memisalluneed/session.json`

Rules:

- During chat, save the current active window to `session.json`.
- Rolled turns are removed from `session.json`.
- Rolled turns are processed by the formation model and written as memories.
- On normal exit, flush the remaining active window to memory.
- After successful normal exit flush, clear the active session file.
- On abnormal interruption, keep `session.json` as a recovery point.

This preserves usability without turning the session file into a permanent chat log.

## Session Turn Structure

One turn is:

> user message + assistant reply + recalled memories

Suggested JSON shape:

```json
{
  "id": "uuid",
  "user_message": "...",
  "assistant_message": "...",
  "recalled_memory_ids": ["..."],
  "created_at": "..."
}
```

The stored active window should contain a list of these turns:

```json
{
  "session_id": "uuid",
  "created_at": "...",
  "updated_at": "...",
  "turns": []
}
```

## Recall Behavior

Every user message in `mem chat` should trigger recall by default.

Process:

1. User enters message.
2. System runs existing Phase 1 keyword search.
3. System retrieves top `recall_top_k` memories.
4. Recalled memories are included in chat model context.
5. Recalled memory ids are stored in the turn.

Default:

```toml
[session]
recall_top_k = 5
```

Phase 2 only uses recall as context inside chat.

## Chat Model Prompt Contract

The chat model should receive:

- a system message describing MEMisALLuNEED as a memory-centric assistant;
- recent active session turns;
- recalled memories for the current user message;
- the current user message.

The prompt should make clear:

- recalled memories may be useful but are not guaranteed to be complete;
- the assistant should answer the user directly;
- the assistant should not claim external knowledge unless it was provided in context.

## Formation Input Contract

Formation model input depends on formation kind.

### Rolling Formation

Rolling formation processes exactly one oldest turn at a time.

Input includes:

```json
{
  "formation_kind": "rolling",
  "turn": {
    "id": "...",
    "user_message": "...",
    "assistant_message": "...",
    "recalled_memory_ids": ["..."],
    "created_at": "..."
  },
  "recalled_memories": [
    {
      "id": "...",
      "type": "knowledge",
      "content": "..."
    }
  ]
}
```

### Exit Flush Formation

On normal exit, remaining active window is processed together.

Input includes:

```json
{
  "formation_kind": "exit_flush",
  "turns": [
    {
      "id": "...",
      "user_message": "...",
      "assistant_message": "...",
      "recalled_memory_ids": ["..."],
      "created_at": "..."
    }
  ]
}
```

## Formation Output Schema

The formation model must return a JSON object:

```json
{
  "memories": [
    {
      "type": "knowledge",
      "content": "...",
      "state": "success",
      "confidence": 0.9,
      "metadata": {
        "source": "chat_session",
        "turn_id": "...",
        "formation_kind": "rolling"
      }
    }
  ]
}
```

### Field Meanings

- `memories`: list of memory candidates generated from this formation event.
- `type`: one of `knowledge`, `experience`, `recall`, or `source`.
- `content`: cleaned and compressed memory content, not raw full transcript.
- `state`: one of `success`, `failed`, `uncertain`, `contradicted`, or `outdated`.
- `confidence`: finite number between `0.0` and `1.0`.
- `metadata`: object containing provenance and formation details.
- `metadata.source`: should be `chat_session` for Phase 2.
- `metadata.turn_id`: source turn id when formation is rolling.
- `metadata.formation_kind`: `rolling` or `exit_flush`.

## Formation Validation

The system must validate formation output before writing memory.

Rules:

- outer value must be an object;
- `memories` must exist;
- `memories` must be an array;
- each memory must be an object;
- `type` must be a supported memory type;
- `state` must be a supported memory state;
- `content` must be non-empty;
- `confidence` must be finite and between `0.0` and `1.0`;
- `metadata` must be an object.

Invalid memory candidates should not be written.

If the entire model response is not valid JSON, formation fails for that event.

## Storage Behavior

Valid formation memories are written using the existing `MemoryStore`.

The system should add metadata fields where useful:

- `source = "chat_session"`;
- `session_id`;
- `turn_id`;
- `formation_kind`;
- `recalled_memory_ids`;
- `formed_at`;
- `model_provider`;
- `model_name`.

Phase 2 should not add graph edges yet.

## Error Handling

### Missing Config

If `.memisalluneed/config.toml` does not exist and `--config` is not provided, `mem chat` should print a clear error explaining how to create config from `config.example.toml`.

### Missing API Key

If the configured API key environment variable is missing, `mem chat` should print a clear provider-specific error.

### Chat Model Failure

If the chat model request fails:

- do not create a completed turn;
- keep active session unchanged;
- print a clear error.

### Formation Model Failure

If formation fails during rolling:

- do not drop the turn silently;
- keep the turn in session or write a failed memory describing the formation failure;
- print a clear warning.

If formation fails during exit flush:

- keep `session.json` so the user can retry;
- print a clear warning.

### Malformed Formation JSON

Malformed formation output should not crash chat.

The system should:

- reject invalid memories;
- write valid memories when possible;
- report malformed output clearly.

## Testing Plan

Tests must not require network or real API keys.

Use fake model clients or `httpx` mock transports.

Minimum tests:

### Config

- load `config.example.toml`;
- load local config path;
- reject missing required provider;
- apply CLI overrides.

### Model Adapter

- builds OpenAI-compatible request correctly;
- reads API key from env;
- rejects missing API key;
- parses assistant content;
- rejects malformed provider response.

### Session

- creates new session;
- saves active window;
- loads active window;
- clears session on normal exit;
- rolls when `max_turns` exceeded;
- rolls when approximate `max_tokens` exceeded.

### Chat Flow

- user message triggers recall;
- recalled memory ids are stored in turn;
- chat model receives recalled memory content;
- assistant reply is stored in turn.

### Formation

- rolling formation processes one turn;
- exit flush processes remaining active window;
- valid formation JSON writes memories;
- invalid formation JSON does not write memories;
- invalid candidate is rejected;
- valid candidates in mixed output are still written.

### CLI

- `mem chat --clear-session` deletes session file;
- `mem chat --new-session` starts fresh;
- missing config prints clear error;
- fake chat interaction can run with injected or mocked model clients.

## Acceptance Criteria

Phase 2 is complete when:

- `config.example.toml` documents GPT, Kimi, and Qwen providers.
- `mem chat` loads `.memisalluneed/config.toml` by default.
- chat and formation model configs are separate.
- `httpx` OpenAI-compatible provider adapter exists.
- tests do not require real network or API keys.
- each chat turn recalls top-k memories by default.
- each turn stores `user_message`, `assistant_message`, and `recalled_memory_ids`.
- active session keeps only recent turns within `max_turns` and `max_tokens`.
- rolling processes exactly one oldest turn at a time.
- normal exit flushes remaining active window to memory.
- successful normal exit clears active session.
- failed exit flush preserves active session.
- valid formation output writes memory items.
- invalid formation output is rejected safely.
- no embedding column is added to SQLite.
- no vector database is introduced.
