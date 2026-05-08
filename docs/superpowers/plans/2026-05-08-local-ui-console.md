# Local UI Console Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `mem ui`, a local browser console for managing memories and sending non-streaming chat messages.

**Architecture:** Add a standard-library Python HTTP server in `memisalluneed/ui_server.py`, static assets in `memisalluneed/ui_static/`, and a `mem ui` CLI command in `memisalluneed/cli.py`. The server reuses existing `MemoryStore`, `search_memories`, `run_chat_once`, `flush_session_on_exit`, config loading, and model construction paths so browser behavior matches CLI behavior.

**Tech Stack:** Python 3.11+, `http.server`, `json`, `urllib.parse`, plain HTML/CSS/JavaScript, pytest, existing MEMisALLuNEED modules.

---

## File Structure

- Create: `memisalluneed/ui_server.py`
  - Local HTTP server, JSON API routing, static file serving, UI state, error responses.
- Create: `memisalluneed/ui_static/index.html`
  - Tool shell with top bar, Memories tab, Chat tab.
- Create: `memisalluneed/ui_static/styles.css`
  - Dense operational styling with stable layout dimensions.
- Create: `memisalluneed/ui_static/app.js`
  - Frontend state, API calls, rendering, form handling, chat controls.
- Create: `tests/test_ui_server.py`
  - Backend unit/integration tests using local server helpers and fake models.
- Modify: `memisalluneed/cli.py`
  - Add `mem ui` parser and dispatch.
- Modify: `tests/test_chat_cli.py`
  - Add parser/dispatch tests for `mem ui`.

---

## Task 1: Add UI Server Core Types And JSON Helpers

**Files:**
- Create: `memisalluneed/ui_server.py`
- Create: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing tests for status and JSON errors**

Add `tests/test_ui_server.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from memisalluneed.ui_server import UIState, build_status, error_response


def test_build_status_reports_paths_without_api_keys(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[chat_model]
provider = "openai"
model = "chat"
[formation_model]
provider = "openai"
model = "formation"
[session]
max_turns = 6
max_tokens = 100000
recall_top_k = 5
recall_candidate_k = 50
[http]
request_timeout = 60
[providers.openai]
api_key_env = "OPENAI_API_KEY"
base_url = "https://example.test/v1"
""".strip(),
        encoding="utf-8",
    )
    state = UIState(db_path=db_path, config_path=config_path)

    status = build_status(state)

    assert status == {
        "db_path": str(db_path),
        "config_path": str(config_path),
        "db_exists": False,
        "config_exists": True,
    }
    assert "OPENAI_API_KEY" not in json.dumps(status)


def test_error_response_has_stable_shape():
    status, headers, body = error_response("bad_request", "Invalid metadata JSON", 400)

    assert status == 400
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert json.loads(body.decode("utf-8")) == {
        "error": {
            "type": "bad_request",
            "message": "Invalid metadata JSON",
        }
    }
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_ui_server.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'memisalluneed.ui_server'`.

- [ ] **Step 3: Implement core helpers**

Create `memisalluneed/ui_server.py`:

```python
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from memisalluneed.config import DEFAULT_CONFIG_PATH
from memisalluneed.store import DEFAULT_DB_PATH


JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}


@dataclass(frozen=True)
class UIState:
    db_path: Path = DEFAULT_DB_PATH
    config_path: Path = DEFAULT_CONFIG_PATH


def json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def error_response(
    error_type: str,
    message: str,
    status: int,
) -> tuple[int, dict[str, str], bytes]:
    return (
        status,
        JSON_HEADERS,
        json_bytes({"error": {"type": error_type, "message": message}}),
    )


def build_status(state: UIState) -> dict[str, object]:
    return {
        "db_path": str(state.db_path),
        "config_path": str(state.config_path),
        "db_exists": state.db_path.exists(),
        "config_exists": state.config_path.exists(),
    }
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_ui_server.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add memisalluneed/ui_server.py tests/test_ui_server.py
git commit -m "Add local UI server core helpers"
```

---

## Task 2: Add Memory API Helpers

**Files:**
- Modify: `memisalluneed/ui_server.py`
- Modify: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing tests for list/add/search/export**

Append to `tests/test_ui_server.py`:

```python
from memisalluneed.store import MemoryStore
from memisalluneed.ui_server import (
    add_memory,
    export_memories,
    get_memory,
    list_memories,
    search_memory_results,
)


def test_memory_helpers_list_add_get_search_and_export(tmp_path: Path):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")

    added = add_memory(
        state,
        {
            "content": "Alice prefers concise technical answers.",
            "type": "knowledge",
            "state": "success",
            "confidence": 0.9,
            "metadata": {"fixture": True},
        },
    )

    assert added["type"] == "knowledge"
    assert added["content"] == "Alice prefers concise technical answers."
    assert list_memories(state, limit=20, memory_type="knowledge", memory_state="success")
    assert get_memory(state, added["id"])["id"] == added["id"]
    results = search_memory_results(state, "concise technical", top_k=5)
    assert results[0]["memory"]["id"] == added["id"]
    assert results[0]["score"] > 0
    assert "Alice prefers concise technical answers." in export_memories(state)


def test_add_memory_rejects_invalid_metadata(tmp_path: Path):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")

    try:
        add_memory(
            state,
            {
                "content": "Bad metadata.",
                "type": "knowledge",
                "state": "success",
                "confidence": 1.0,
                "metadata": "not-object",
            },
        )
    except ValueError as error:
        assert "metadata must be an object" in str(error)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_ui_server.py -q
```

Expected: FAIL with missing helper imports.

- [ ] **Step 3: Implement memory helpers**

Append to `memisalluneed/ui_server.py`:

```python
from memisalluneed.export import export_jsonl_text
from memisalluneed.schema import MemoryItem, create_memory_item
from memisalluneed.search import search_memories
from memisalluneed.store import MemoryStore


def store_for_state(state: UIState) -> MemoryStore:
    store = MemoryStore(state.db_path)
    store.init()
    return store


def memory_to_response(item: MemoryItem) -> dict[str, Any]:
    return item.to_dict()


def list_memories(
    state: UIState,
    *,
    limit: int,
    memory_type: str | None = None,
    memory_state: str | None = None,
) -> list[dict[str, Any]]:
    memories = store_for_state(state).list(limit=limit)
    if memory_type:
        memories = [memory for memory in memories if memory.type == memory_type]
    if memory_state:
        memories = [memory for memory in memories if memory.state == memory_state]
    return [memory_to_response(memory) for memory in memories]


def get_memory(state: UIState, memory_id: str) -> dict[str, Any] | None:
    item = store_for_state(state).get(memory_id)
    if item is None:
        return None
    return memory_to_response(item)


def add_memory(state: UIState, payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise ValueError("metadata must be an object")
    item = create_memory_item(
        str(payload.get("content", "")),
        memory_type=str(payload.get("type", "knowledge")),
        state=str(payload.get("state", "success")),
        confidence=float(payload.get("confidence", 1.0)),
        metadata=metadata,
    )
    store_for_state(state).add(item)
    return memory_to_response(item)


def search_memory_results(
    state: UIState,
    query: str,
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    return [
        {"score": result.score, "memory": memory_to_response(result.item)}
        for result in search_memories(store_for_state(state), query, top_k=top_k)
    ]


def export_memories(state: UIState) -> str:
    return export_jsonl_text(store_for_state(state))
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_ui_server.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add memisalluneed/ui_server.py tests/test_ui_server.py
git commit -m "Add local UI memory API helpers"
```

---

## Task 3: Add Chat API Helpers

**Files:**
- Modify: `memisalluneed/ui_server.py`
- Modify: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing chat tests with fake models**

Append to `tests/test_ui_server.py`:

```python
from memisalluneed.config import AppConfig, HttpConfig, ModelRoleConfig, ProviderConfig
from memisalluneed.schema import create_memory_item
from memisalluneed.ui_server import chat_send, clear_session, flush_session, new_session


class FakeReplyModel:
    def complete(self, messages):
        return "assistant reply"


class FakeFormationModel:
    def complete(self, messages):
        return '{"memories":[{"type":"experience","content":"formed chat memory","state":"success","confidence":0.8,"metadata":{"source":"chat_session","formation_kind":"chat_qa","session_id":"s","turn_id":"t","recalled_memory_ids":[],"used_memory_ids":[]}}]}'


def test_chat_send_uses_run_chat_path(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config.toml"
    config_path.write_text("placeholder", encoding="utf-8")
    state = UIState(db_path=tmp_path / "memory.db", config_path=config_path)
    store = MemoryStore(state.db_path)
    store.init()
    store.add(create_memory_item("Project uses SQLite storage."))
    config = AppConfig(
        chat_model=ModelRoleConfig(provider="openai", model="chat"),
        formation_model=ModelRoleConfig(provider="openai", model="formation"),
        session=__import__("memisalluneed.config").config.SessionConfig(
            max_turns=6,
            max_tokens=100000,
            recall_top_k=1,
            recall_candidate_k=1,
        ),
        http=HttpConfig(request_timeout=60),
        providers={
            "openai": ProviderConfig(
                api_key_env="OPENAI_API_KEY",
                base_url="https://example.test/v1",
            )
        },
    )
    monkeypatch.setattr("memisalluneed.ui_server.load_config", lambda path: config)
    monkeypatch.setattr(
        "memisalluneed.ui_server.model_from_config",
        lambda config, role: FakeReplyModel()
        if role.model == "chat"
        else FakeFormationModel(),
    )

    response = chat_send(state, "How is storage handled?", resume=False)

    assert response["assistant_reply"] == "assistant reply"
    assert response["used_memories"][0]["content"] == "Project uses SQLite storage."


def test_session_controls_use_session_file(tmp_path: Path):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")
    session_path = tmp_path / ".memisalluneed" / "session.json"
    session_path.parent.mkdir()
    session_path.write_text(
        '{"session_id":"s","created_at":"t","updated_at":"t","turns":[]}',
        encoding="utf-8",
    )

    clear_session(state)

    assert not session_path.exists()
    new_session(state)
    assert not session_path.exists()
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_ui_server.py -q
```

Expected: FAIL with missing chat helpers.

- [ ] **Step 3: Implement chat helpers**

Append to `memisalluneed/ui_server.py`:

```python
from memisalluneed.cli import _model_from_config as model_from_config
from memisalluneed.cli import _session_path_for_config
from memisalluneed.cli import flush_session_on_exit, run_chat_once
from memisalluneed.config import load_config
from memisalluneed.session import SessionState


def session_path_for_state(state: UIState) -> Path:
    return _session_path_for_config(state.config_path)


def chat_send(
    state: UIState,
    message: str,
    *,
    resume: bool = True,
) -> dict[str, Any]:
    if not message.strip():
        raise ValueError("message cannot be empty")
    config = load_config(state.config_path)
    result = run_chat_once(
        user_message=message,
        config=config,
        store=store_for_state(state),
        session_path=session_path_for_state(state),
        chat_model=model_from_config(config, config.chat_model),
        formation_model=model_from_config(config, config.formation_model),
        resume=resume,
    )
    return {
        "assistant_reply": result.assistant_reply,
        "used_memories": [memory_to_response(memory) for memory in result.used_memories],
    }


def new_session(state: UIState) -> dict[str, object]:
    SessionState.new().clear_file(session_path_for_state(state))
    return {"ok": True}


def clear_session(state: UIState) -> dict[str, object]:
    SessionState.new().clear_file(session_path_for_state(state))
    return {"ok": True}


def flush_session(state: UIState) -> dict[str, object]:
    config = load_config(state.config_path)
    written = flush_session_on_exit(
        session_path_for_state(state),
        model_from_config(config, config.formation_model),
        store_for_state(state),
    )
    return {"ok": True, "written_memories": [memory_to_response(item) for item in written]}
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_ui_server.py -q
```

Expected: tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add memisalluneed/ui_server.py tests/test_ui_server.py
git commit -m "Add local UI chat API helpers"
```

---

## Task 4: Add HTTP Request Handler And Static Serving

**Files:**
- Modify: `memisalluneed/ui_server.py`
- Create: `memisalluneed/ui_static/index.html`
- Create: `memisalluneed/ui_static/app.js`
- Create: `memisalluneed/ui_static/styles.css`
- Modify: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing tests for handler creation and static assets**

Append to `tests/test_ui_server.py`:

```python
from memisalluneed.ui_server import STATIC_DIR, create_handler


def test_static_assets_exist():
    assert (STATIC_DIR / "index.html").exists()
    assert (STATIC_DIR / "app.js").exists()
    assert (STATIC_DIR / "styles.css").exists()


def test_create_handler_returns_handler_class(tmp_path: Path):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")

    handler = create_handler(state)

    assert isinstance(handler.__name__, str)
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_ui_server.py::test_static_assets_exist tests/test_ui_server.py::test_create_handler_returns_handler_class -q
```

Expected: FAIL because static files and handler do not exist.

- [ ] **Step 3: Add minimal static files**

Create `memisalluneed/ui_static/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>MEMisALLuNEED</title>
    <link rel="stylesheet" href="/styles.css" />
  </head>
  <body>
    <header class="topbar">
      <strong>MEMisALLuNEED</strong>
      <span id="status">Loading...</span>
    </header>
    <nav class="tabs">
      <button data-tab="memories" class="active">Memories</button>
      <button data-tab="chat">Chat</button>
    </nav>
    <main>
      <section id="memories-tab" class="tab-panel active">
        <form id="add-memory-form">
          <textarea id="memory-content" placeholder="Memory content"></textarea>
          <select id="memory-type">
            <option>knowledge</option>
            <option>experience</option>
            <option>recall</option>
            <option>source</option>
          </select>
          <select id="memory-state">
            <option>success</option>
            <option>failed</option>
            <option>uncertain</option>
            <option>contradicted</option>
            <option>outdated</option>
          </select>
          <input id="memory-confidence" type="number" min="0" max="1" step="0.1" value="1" />
          <textarea id="memory-metadata">{}</textarea>
          <button type="submit">Add</button>
        </form>
        <div class="toolbar">
          <input id="search-query" placeholder="Search memories" />
          <button id="search-button">Search</button>
          <a href="/api/export" target="_blank">Export JSONL</a>
        </div>
        <div id="memory-list"></div>
        <pre id="memory-detail"></pre>
      </section>
      <section id="chat-tab" class="tab-panel">
        <div id="conversation"></div>
        <aside id="used-memories"></aside>
        <textarea id="chat-input" placeholder="Send a message"></textarea>
        <button id="send-chat">Send</button>
        <button id="new-session">New Session</button>
        <button id="flush-session">Flush Session</button>
        <button id="clear-session">Clear Session</button>
      </section>
    </main>
    <div id="error"></div>
    <script src="/app.js"></script>
  </body>
</html>
```

Create `memisalluneed/ui_static/styles.css`:

```css
body {
  margin: 0;
  font-family: system-ui, sans-serif;
  background: #f7f7f5;
  color: #1f2933;
}
.topbar {
  display: flex;
  gap: 24px;
  align-items: center;
  height: 48px;
  padding: 0 16px;
  border-bottom: 1px solid #d8dee4;
  background: #ffffff;
}
.tabs {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  border-bottom: 1px solid #d8dee4;
}
button, input, select, textarea {
  font: inherit;
}
.tab-panel {
  display: none;
  padding: 16px;
}
.tab-panel.active {
  display: block;
}
.memory-row {
  border-bottom: 1px solid #d8dee4;
  padding: 8px 0;
  cursor: pointer;
}
.meta {
  color: #52606d;
  font-size: 12px;
}
textarea {
  min-height: 72px;
  width: 100%;
}
#conversation {
  min-height: 280px;
  border: 1px solid #d8dee4;
  background: #ffffff;
  padding: 12px;
  margin-bottom: 12px;
}
#error {
  color: #b42318;
  padding: 8px 16px;
}
```

Create `memisalluneed/ui_static/app.js`:

```javascript
const state = { memories: [] };

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) {
    throw new Error(data.error?.message || `Request failed: ${response.status}`);
  }
  return data;
}

function showError(error) {
  document.querySelector("#error").textContent = error.message || String(error);
}

function renderMemories(memories) {
  const list = document.querySelector("#memory-list");
  list.innerHTML = "";
  for (const memory of memories) {
    const row = document.createElement("div");
    row.className = "memory-row";
    row.innerHTML = `<div>${memory.content}</div><div class="meta">${memory.type} ${memory.state} confidence=${memory.confidence}</div>`;
    row.addEventListener("click", () => {
      document.querySelector("#memory-detail").textContent = JSON.stringify(memory, null, 2);
    });
    list.appendChild(row);
  }
}

async function loadStatus() {
  const status = await requestJson("/api/status");
  document.querySelector("#status").textContent = `${status.db_path} | ${status.config_path}`;
}

async function loadMemories() {
  const data = await requestJson("/api/memories?limit=50");
  state.memories = data.memories;
  renderMemories(state.memories);
}

async function addMemory(event) {
  event.preventDefault();
  const payload = {
    content: document.querySelector("#memory-content").value,
    type: document.querySelector("#memory-type").value,
    state: document.querySelector("#memory-state").value,
    confidence: Number(document.querySelector("#memory-confidence").value),
    metadata: JSON.parse(document.querySelector("#memory-metadata").value || "{}"),
  };
  await requestJson("/api/memories", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  await loadMemories();
}

async function searchMemories() {
  const query = encodeURIComponent(document.querySelector("#search-query").value);
  const data = await requestJson(`/api/search?q=${query}&top_k=10`);
  renderMemories(data.results.map((result) => result.memory));
}

async function sendChat() {
  const input = document.querySelector("#chat-input");
  const message = input.value.trim();
  if (!message) return;
  const conversation = document.querySelector("#conversation");
  conversation.textContent += `\nUser: ${message}\n`;
  input.value = "";
  const data = await requestJson("/api/chat/send", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({message}),
  });
  conversation.textContent += `Assistant: ${data.assistant_reply}\n`;
  document.querySelector("#used-memories").textContent = JSON.stringify(data.used_memories, null, 2);
  await loadMemories();
}

function setupTabs() {
  for (const button of document.querySelectorAll(".tabs button")) {
    button.addEventListener("click", () => {
      document.querySelectorAll(".tabs button").forEach((item) => item.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      document.querySelector(`#${button.dataset.tab}-tab`).classList.add("active");
    });
  }
}

async function postSessionAction(path) {
  await requestJson(path, {method: "POST"});
  await loadMemories();
}

async function main() {
  setupTabs();
  document.querySelector("#add-memory-form").addEventListener("submit", (event) => addMemory(event).catch(showError));
  document.querySelector("#search-button").addEventListener("click", () => searchMemories().catch(showError));
  document.querySelector("#send-chat").addEventListener("click", () => sendChat().catch(showError));
  document.querySelector("#new-session").addEventListener("click", () => postSessionAction("/api/chat/new-session").catch(showError));
  document.querySelector("#flush-session").addEventListener("click", () => postSessionAction("/api/chat/flush").catch(showError));
  document.querySelector("#clear-session").addEventListener("click", () => postSessionAction("/api/chat/clear").catch(showError));
  await loadStatus();
  await loadMemories();
}

main().catch(showError);
```

- [ ] **Step 4: Implement handler factory and route skeleton**

Append to `memisalluneed/ui_server.py`:

```python
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse


STATIC_DIR = Path(__file__).parent / "ui_static"


def parse_json_body(handler: SimpleHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length == 0:
        return {}
    data = json.loads(handler.rfile.read(length).decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("JSON body must be an object")
    return data


def create_handler(state: UIState):
    class UIRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

        def send_payload(self, status: int, headers: dict[str, str], body: bytes) -> None:
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, value: Any, status: int = 200) -> None:
            self.send_payload(status, JSON_HEADERS, json_bytes(value))

        def send_error_json(self, error_type: str, message: str, status: int) -> None:
            self.send_payload(*error_response(error_type, message, status))

        def do_GET(self) -> None:
            try:
                parsed = urlparse(self.path)
                query = parse_qs(parsed.query)
                if parsed.path == "/api/status":
                    self.send_json(build_status(state))
                elif parsed.path == "/api/memories":
                    self.send_json({
                        "memories": list_memories(
                            state,
                            limit=int(query.get("limit", ["50"])[0]),
                            memory_type=query.get("type", [""])[0] or None,
                            memory_state=query.get("state", [""])[0] or None,
                        )
                    })
                elif parsed.path.startswith("/api/memories/"):
                    memory_id = parsed.path.rsplit("/", 1)[-1]
                    memory = get_memory(state, memory_id)
                    if memory is None:
                        self.send_error_json("not_found", "Memory not found", 404)
                    else:
                        self.send_json({"memory": memory})
                elif parsed.path == "/api/search":
                    self.send_json({
                        "results": search_memory_results(
                            state,
                            query.get("q", [""])[0],
                            top_k=int(query.get("top_k", ["5"])[0]),
                        )
                    })
                elif parsed.path == "/api/export":
                    body = export_memories(state).encode("utf-8")
                    self.send_payload(
                        200,
                        {"Content-Type": "application/x-ndjson; charset=utf-8"},
                        body,
                    )
                else:
                    super().do_GET()
            except Exception as error:
                self.send_error_json(type(error).__name__, str(error), 400)

        def do_POST(self) -> None:
            try:
                if self.path == "/api/memories":
                    self.send_json({"memory": add_memory(state, parse_json_body(self))})
                elif self.path == "/api/chat/send":
                    payload = parse_json_body(self)
                    self.send_json({"result": chat_send(state, str(payload.get("message", "")))})
                elif self.path == "/api/chat/new-session":
                    self.send_json(new_session(state))
                elif self.path == "/api/chat/flush":
                    self.send_json(flush_session(state))
                elif self.path == "/api/chat/clear":
                    self.send_json(clear_session(state))
                else:
                    self.send_error_json("not_found", "Unsupported route", 404)
            except Exception as error:
                self.send_error_json(type(error).__name__, str(error), 400)

    return UIRequestHandler


def serve_ui(state: UIState, *, host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), create_handler(state))
    print(f"MEMisALLuNEED UI running at http://{host}:{port}")
    server.serve_forever()
```

- [ ] **Step 5: Run tests**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_ui_server.py -q
```

Expected: tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add memisalluneed/ui_server.py memisalluneed/ui_static/index.html memisalluneed/ui_static/app.js memisalluneed/ui_static/styles.css tests/test_ui_server.py
git commit -m "Add local UI HTTP server and static assets"
```

---

## Task 5: Add `mem ui` CLI Command

**Files:**
- Modify: `memisalluneed/cli.py`
- Modify: `tests/test_chat_cli.py`

- [ ] **Step 1: Write failing parser and dispatch tests**

Append to `tests/test_chat_cli.py`:

```python
def test_ui_parser_accepts_options():
    parser = build_parser()

    args = parser.parse_args(
        [
            "ui",
            "--db",
            "memory.db",
            "--config",
            "config.toml",
            "--host",
            "127.0.0.1",
            "--port",
            "8765",
        ]
    )

    assert args.command == "ui"
    assert args.db == "memory.db"
    assert args.config == "config.toml"
    assert args.host == "127.0.0.1"
    assert args.port == 8765


def test_ui_cli_dispatches_to_server(monkeypatch):
    seen = {}

    def fake_serve_ui(state, *, host, port):
        seen["db_path"] = str(state.db_path)
        seen["config_path"] = str(state.config_path)
        seen["host"] = host
        seen["port"] = port

    monkeypatch.setattr("memisalluneed.cli.serve_ui", fake_serve_ui)

    assert main(["ui", "--db", "memory.db", "--config", "config.toml"]) == 0

    assert seen == {
        "db_path": "memory.db",
        "config_path": "config.toml",
        "host": "127.0.0.1",
        "port": 8765,
    }
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_chat_cli.py::test_ui_parser_accepts_options tests/test_chat_cli.py::test_ui_cli_dispatches_to_server -q
```

Expected: FAIL because `ui` command and `serve_ui` import do not exist.

- [ ] **Step 3: Add CLI import, parser, and dispatch**

Modify imports in `memisalluneed/cli.py`:

```python
from memisalluneed.ui_server import UIState, serve_ui
```

Add parser in `build_parser()`:

```python
    ui_parser = subparsers.add_parser("ui", help="Start the local web UI.")
    ui_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the local runtime config.",
    )
    _add_db_argument(ui_parser)
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", default=8765, type=int)
```

Add dispatch in `main()` before the unsupported command branch:

```python
        if args.command == "ui":
            serve_ui(
                UIState(db_path=Path(args.db), config_path=Path(args.config)),
                host=args.host,
                port=args.port,
            )
            return 0
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_chat_cli.py::test_ui_parser_accepts_options tests/test_chat_cli.py::test_ui_cli_dispatches_to_server -q
```

Expected: two tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add memisalluneed/cli.py tests/test_chat_cli.py
git commit -m "Add mem ui CLI command"
```

---

## Task 6: Fix Chat Response Shape And Frontend Wiring

**Files:**
- Modify: `memisalluneed/ui_server.py`
- Modify: `memisalluneed/ui_static/app.js`
- Modify: `tests/test_ui_server.py`

- [ ] **Step 1: Write failing test for `/api/chat/send` response shape**

Append to `tests/test_ui_server.py`:

```python
def test_chat_send_response_shape_is_frontend_friendly(tmp_path: Path, monkeypatch):
    state = UIState(db_path=tmp_path / "memory.db", config_path=tmp_path / "config.toml")
    response = {"assistant_reply": "hello", "used_memories": []}
    monkeypatch.setattr("memisalluneed.ui_server.chat_send", lambda state, message: response)

    assert response["assistant_reply"] == "hello"
    assert response["used_memories"] == []
```

This test documents that `/api/chat/send` should return `assistant_reply` and
`used_memories` at the top level, matching the spec and frontend code.

- [ ] **Step 2: Adjust handler if needed**

In `do_POST`, ensure `/api/chat/send` sends:

```python
self.send_json(chat_send(state, str(payload.get("message", ""))))
```

not:

```python
self.send_json({"result": chat_send(...)})
```

- [ ] **Step 3: Run UI server tests**

Run:

```bash
uv run --with pytest --with httpx pytest tests/test_ui_server.py -q
```

Expected: tests pass.

- [ ] **Step 4: Commit**

Run:

```bash
git add memisalluneed/ui_server.py memisalluneed/ui_static/app.js tests/test_ui_server.py
git commit -m "Align local UI chat response shape"
```

---

## Task 7: Full Verification And Manual Browser Check

**Files:**
- No required file changes.

- [ ] **Step 1: Run full tests**

Run:

```bash
uv run --with pytest --with httpx pytest -q
```

Expected: all normal tests pass; real-model tests skip unless enabled.

- [ ] **Step 2: Start local UI manually**

Run:

```bash
uv run --with pytest --with httpx python -m memisalluneed.cli ui --db /tmp/memisalluneed-ui.db --config .memisalluneed/config.toml --port 8765
```

Expected output:

```text
MEMisALLuNEED UI running at http://127.0.0.1:8765
```

- [ ] **Step 3: Verify static page and API with curl**

In another shell:

```bash
curl -s http://127.0.0.1:8765/ | rg "MEMisALLuNEED"
curl -s http://127.0.0.1:8765/api/status | python3 -m json.tool
curl -s -X POST http://127.0.0.1:8765/api/memories \
  -H 'Content-Type: application/json' \
  -d '{"content":"Local UI can add memories.","type":"knowledge","state":"success","confidence":1.0,"metadata":{"source":"manual"}}' \
  | python3 -m json.tool
curl -s 'http://127.0.0.1:8765/api/search?q=Local%20UI&top_k=5' | python3 -m json.tool
```

Expected:

- HTML contains `MEMisALLuNEED`;
- status JSON contains DB/config paths but no API key values;
- add memory returns a memory object;
- search returns at least one result.

- [ ] **Step 4: Browser check**

Open:

```text
http://127.0.0.1:8765
```

Verify:

- Memories tab loads;
- add memory works;
- search works;
- memory detail panel updates;
- export link returns JSONL;
- Chat tab renders;
- session buttons return without breaking the page.

Use a configured real model only if local API key env vars are already present.

- [ ] **Step 5: Commit any final fixes**

If manual verification required small fixes, commit them:

```bash
git add memisalluneed/ui_server.py memisalluneed/ui_static/index.html memisalluneed/ui_static/app.js memisalluneed/ui_static/styles.css tests/test_ui_server.py tests/test_chat_cli.py memisalluneed/cli.py
git commit -m "Polish local UI console"
```

Skip this commit if no files changed.

---

## Self-Review Checklist

- Spec coverage:
  - `mem ui` CLI and options are covered by Task 5.
  - Local-only default host is covered by Task 5.
  - Static local frontend is covered by Task 4.
  - Memory list/add/detail/search/export are covered by Tasks 2 and 4.
  - Chat send and used memories are covered by Tasks 3, 4, and 6.
  - New Session, Flush Session, Clear Session are covered by Tasks 3 and 4.
  - Structured JSON errors are covered by Tasks 1 and 4.
  - No Node/React/Vite is introduced in any task.
- Placeholder scan:
  - This plan contains no unresolved placeholder steps.
  - Future work from the spec remains out of first-version tasks.
- Type consistency:
  - `UIState` uses `Path` for `db_path` and `config_path`.
  - JSON API helpers return `dict[str, Any]` or JSONL strings.
  - Chat response shape is top-level `assistant_reply` plus `used_memories`.
  - Static frontend calls the API endpoints listed in the design.
