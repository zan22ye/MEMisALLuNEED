from __future__ import annotations

import json
from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from memisalluneed.cli import _model_from_config as model_from_config
from memisalluneed.cli import _session_path_for_config
from memisalluneed.cli import flush_session_on_exit, run_chat_once
from memisalluneed.config import DEFAULT_CONFIG_PATH
from memisalluneed.config import load_config
from memisalluneed.export import export_jsonl_text
from memisalluneed.schema import MemoryItem, create_memory_item
from memisalluneed.search import search_memories
from memisalluneed.session import SessionState
from memisalluneed.store import DEFAULT_DB_PATH
from memisalluneed.store import MemoryStore


JSON_HEADERS = {"Content-Type": "application/json; charset=utf-8"}
STATIC_DIR = Path(__file__).parent / "ui_static"


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
    return {
        "ok": True,
        "written_memories": [memory_to_response(item) for item in written],
    }


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

        def send_payload(
            self,
            status: int,
            headers: dict[str, str],
            body: bytes,
        ) -> None:
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
                    self.send_json(
                        {
                            "memories": list_memories(
                                state,
                                limit=int(query.get("limit", ["50"])[0]),
                                memory_type=query.get("type", [""])[0] or None,
                                memory_state=query.get("state", [""])[0] or None,
                            )
                        }
                    )
                elif parsed.path.startswith("/api/memories/"):
                    memory_id = parsed.path.rsplit("/", 1)[-1]
                    memory = get_memory(state, memory_id)
                    if memory is None:
                        self.send_error_json("not_found", "Memory not found", 404)
                    else:
                        self.send_json({"memory": memory})
                elif parsed.path == "/api/search":
                    self.send_json(
                        {
                            "results": search_memory_results(
                                state,
                                query.get("q", [""])[0],
                                top_k=int(query.get("top_k", ["5"])[0]),
                            )
                        }
                    )
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
                    self.send_json(chat_send(state, str(payload.get("message", ""))))
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
