from __future__ import annotations

import argparse
import errno
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from memisalluneed.config import AppConfig, ConfigOverrides, DEFAULT_CONFIG_PATH
from memisalluneed.config import load_config
from memisalluneed.export import export_jsonl, export_jsonl_text
from memisalluneed.formation import FormationService
from memisalluneed.integration import integrate_answer_trace
from memisalluneed.integration import integrate_host_evidence
from memisalluneed.integration import integrate_source_reference
from memisalluneed.models.base import ChatMessage, ChatModel
from memisalluneed.resolution import ResolvedMemoryContext
from memisalluneed.resolution import resolve_current_memories
from memisalluneed.schema import create_memory_item
from memisalluneed.schema import utc_now
from memisalluneed.search import search_memories
from memisalluneed.session import DEFAULT_SESSION_PATH, SessionState, SessionTurn
from memisalluneed.store import DEFAULT_DB_PATH, MemoryStore
from memisalluneed.ui_server import UIState, serve_ui


def _add_db_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to the SQLite memory database.",
    )


def _add_integration_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the local runtime config.",
    )
    _add_db_argument(parser)
    parser.add_argument("--host-agent")
    parser.add_argument("--metadata", default="{}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mem")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a memory database.")
    _add_db_argument(init_parser)

    add_parser = subparsers.add_parser("add", help="Add a memory item.")
    add_parser.add_argument("content", nargs="+")
    add_parser.add_argument("--type", default="knowledge", dest="memory_type")
    add_parser.add_argument("--state", default="success")
    add_parser.add_argument("--confidence", default=1.0, type=float)
    add_parser.add_argument("--metadata", default="{}")
    _add_db_argument(add_parser)

    list_parser = subparsers.add_parser("list", help="List memory items.")
    list_parser.add_argument("--limit", default=20, type=int)
    _add_db_argument(list_parser)

    show_parser = subparsers.add_parser("show", help="Show one memory item.")
    show_parser.add_argument("id")
    show_parser.add_argument("--json", action="store_true", dest="as_json")
    _add_db_argument(show_parser)

    search_parser = subparsers.add_parser("search", help="Search memory items.")
    search_parser.add_argument("query", nargs="+")
    search_parser.add_argument("--top-k", default=5, type=int)
    _add_db_argument(search_parser)

    export_parser = subparsers.add_parser("export", help="Export memory items as JSONL.")
    export_parser.add_argument("--output")
    _add_db_argument(export_parser)

    chat_parser = subparsers.add_parser("chat", help="Start a memory-centric chat.")
    chat_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the local runtime config.",
    )
    _add_db_argument(chat_parser)
    chat_parser.add_argument("--chat-provider")
    chat_parser.add_argument("--chat-model")
    chat_parser.add_argument("--formation-provider")
    chat_parser.add_argument("--formation-model")
    chat_parser.add_argument("--max-turns", type=int)
    chat_parser.add_argument("--max-tokens", type=int)
    chat_parser.add_argument("--recall-top-k", type=int)
    chat_parser.add_argument("--recall-candidate-k", type=int)
    chat_parser.add_argument("--new-session", action="store_true")
    chat_parser.add_argument("--clear-session", action="store_true")
    chat_parser.add_argument("--no-resume", action="store_true")
    chat_parser.add_argument(
        "--show-memory-trace",
        action="store_true",
        help="Print the memories used after each assistant reply.",
    )

    ui_parser = subparsers.add_parser("ui", help="Start the local web UI.")
    ui_parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the local runtime config.",
    )
    _add_db_argument(ui_parser)
    ui_parser.add_argument("--host", default="127.0.0.1")
    ui_parser.add_argument("--port", default=8765, type=int)

    integrate_source_parser = subparsers.add_parser(
        "integrate-source",
        help="Integrate a host-supplied source reference.",
    )
    _add_integration_common_arguments(integrate_source_parser)
    integrate_source_parser.add_argument("--source-uri", required=True)
    integrate_source_parser.add_argument("--source-title")
    integrate_source_parser.add_argument("--retrieved-at")

    integrate_evidence_parser = subparsers.add_parser(
        "integrate-evidence",
        help="Integrate host-supplied evidence.",
    )
    _add_integration_common_arguments(integrate_evidence_parser)
    integrate_evidence_parser.add_argument("--evidence", required=True)
    integrate_evidence_parser.add_argument("--query")
    integrate_evidence_parser.add_argument(
        "--source-id",
        action="append",
        dest="source_ids",
    )
    integrate_evidence_parser.add_argument("--confidence", type=float, default=1.0)
    integrate_evidence_parser.add_argument("--state", default="success")

    integrate_answer_parser = subparsers.add_parser(
        "integrate-answer",
        help="Integrate a host-supplied answer trace.",
    )
    _add_integration_common_arguments(integrate_answer_parser)
    integrate_answer_parser.add_argument("--query", required=True)
    integrate_answer_parser.add_argument("--answer", required=True)
    integrate_answer_parser.add_argument(
        "--evidence-id",
        action="append",
        dest="evidence_ids",
    )
    integrate_answer_parser.add_argument(
        "--source-id",
        action="append",
        dest="source_ids",
    )
    integrate_answer_parser.add_argument(
        "--recalled-memory-id",
        action="append",
        dest="recalled_memory_ids",
    )
    integrate_answer_parser.add_argument("--confidence", type=float, default=1.0)
    integrate_answer_parser.add_argument("--state", default="success")

    return parser


def _preview(content: str, limit: int = 80) -> str:
    compact = " ".join(content.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[: limit - 1]}…"


def _parse_metadata(raw_metadata: str) -> dict[str, object]:
    try:
        metadata = json.loads(raw_metadata)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid metadata JSON: {error.msg}") from error

    if not isinstance(metadata, dict):
        raise ValueError("Invalid metadata JSON: value must be an object")

    return metadata


def _join_text_parts(parts: str | Sequence[str]) -> str:
    if isinstance(parts, str):
        return parts
    return " ".join(parts)


def _print_item(item) -> None:
    print(f"id: {item.id}")
    print(f"type: {item.type}")
    print(f"state: {item.state}")
    print(f"confidence: {item.confidence}")
    print(f"created_at: {item.created_at}")
    print(f"updated_at: {item.updated_at}")
    print(f"usage_count: {item.usage_count}")
    print(f"last_recalled_at: {item.last_recalled_at}")
    print(f"metadata: {json.dumps(dict(item.metadata), ensure_ascii=False, sort_keys=True)}")
    print(f"content: {item.content}")


def _print_written_ids(memories) -> None:
    for memory in memories:
        print(memory.id)


@dataclass(frozen=True)
class ChatRunResult:
    assistant_reply: str
    used_memories: list


def format_memory_trace(used_memories) -> str:
    if not used_memories:
        return "Used memories:\n- none"

    lines = [
        "Used memories:",
        *[
            (
                f"- {memory.id} {memory.type} {memory.state} "
                f"confidence={memory.confidence:g}"
            )
            for memory in used_memories
        ],
    ]
    return "\n".join(lines)


def build_chat_messages(
    active_turns: list[SessionTurn],
    resolved_context: ResolvedMemoryContext,
    user_message: str,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = [
        {
            "role": "system",
            "content": (
                "You are MEMisALLuNEED, a memory-centric assistant. "
                "Recalled memories may be useful but are not guaranteed to be complete. "
                "When primary and older relevant memories conflict, prefer primary memories. "
                "Older relevant memories are still useful context but may be less current. "
                "Use timestamp-unresolved memories cautiously. "
                "Answer the user directly. Do not claim external knowledge unless it "
                "was provided in the current context."
            ),
        }
    ]
    for turn in active_turns:
        messages.append({"role": "user", "content": turn.user_message})
        messages.append({"role": "assistant", "content": turn.assistant_message})

    def format_result(result) -> str:
        item = result.item
        return (
            f"- {item.id} ({item.type}, {item.state}, "
            f"confidence={item.confidence:g}, created_at={item.created_at}): "
            f"{item.content}"
        )

    sections = ["Resolved memory context:"]
    sections.append("Primary relevant memories:")
    sections.extend(
        [format_result(result) for result in resolved_context.primary] or ["- none"]
    )
    sections.append("Older relevant memories:")
    sections.extend(
        [format_result(result) for result in resolved_context.older_relevant]
        or ["- none"]
    )
    sections.append("Timestamp-unresolved memories:")
    sections.extend(
        [format_result(result) for result in resolved_context.unresolved_time]
        or ["- none"]
    )
    messages.append({"role": "system", "content": "\n".join(sections)})
    messages.append({"role": "user", "content": user_message})
    return messages


def run_chat_once(
    *,
    user_message: str,
    config: AppConfig,
    store: MemoryStore,
    session_path: str | Path,
    chat_model: ChatModel,
    formation_model: ChatModel,
    resume: bool = True,
) -> ChatRunResult:
    session = SessionState.load(session_path) if resume else SessionState.new()
    recalled_results = search_memories(
        store,
        user_message,
        top_k=config.session.recall_candidate_k,
    )
    resolved_context = resolve_current_memories(
        recalled_results,
        final_k=config.session.recall_top_k,
    )
    prompt_results = (
        resolved_context.primary
        + resolved_context.older_relevant
        + resolved_context.unresolved_time
    )
    used_memories = [result.item for result in prompt_results]
    assistant_reply = chat_model.complete(
        build_chat_messages(session.turns, resolved_context, user_message)
    )
    turn = SessionTurn(
        id=str(uuid4()),
        user_message=user_message,
        assistant_message=assistant_reply,
        recalled_memory_ids=[memory.id for memory in used_memories],
        created_at=utc_now(),
    )
    session.add_turn(turn)
    session.save(session_path)

    formation = FormationService(model=formation_model, store=store)
    rolled_turns = session.roll_excess(
        max_turns=config.session.max_turns,
        max_tokens=config.session.max_tokens,
    )
    for rolled_turn in rolled_turns:
        recalled_memories = [
            memory
            for memory_id in rolled_turn.recalled_memory_ids
            if (memory := store.get(memory_id)) is not None
        ]
        formation.form_from_chat_qa_turn(
            session_id=session.session_id,
            turn=rolled_turn,
            recalled_memories=recalled_memories,
        )
    session.save(session_path)
    return ChatRunResult(
        assistant_reply=assistant_reply,
        used_memories=used_memories,
    )


def flush_session_on_exit(
    session_path: str | Path,
    formation_model: ChatModel,
    store: MemoryStore,
) -> list:
    session = SessionState.load(session_path)
    if not session.turns:
        session.clear_file(session_path)
        return []

    formation = FormationService(model=formation_model, store=store)
    written = []
    for turn in session.turns:
        recalled_memories = [
            memory
            for memory_id in turn.recalled_memory_ids
            if (memory := store.get(memory_id)) is not None
        ]
        written.extend(
            formation.form_from_chat_qa_turn(
                session_id=session.session_id,
                turn=turn,
                recalled_memories=recalled_memories,
            )
        )
    session.clear_file(session_path)
    return written


def _config_overrides_from_args(args) -> ConfigOverrides:
    return ConfigOverrides(
        chat_provider=args.chat_provider,
        chat_model=args.chat_model,
        formation_provider=args.formation_provider,
        formation_model=args.formation_model,
        max_turns=args.max_turns,
        max_tokens=args.max_tokens,
        recall_top_k=args.recall_top_k,
        recall_candidate_k=args.recall_candidate_k,
    )


def _session_path_for_config(config_path: str | Path) -> Path:
    path = Path(config_path)
    if path == DEFAULT_CONFIG_PATH or path.parent.name == ".memisalluneed":
        return path.parent / "session.json"
    return path.parent / ".memisalluneed" / "session.json"


def _model_from_config(config: AppConfig, role) -> ChatModel:
    from memisalluneed.models.openai_compatible import OpenAICompatibleChatModel

    return OpenAICompatibleChatModel(
        provider=config.providers[role.provider],
        model=role.model,
        timeout=config.http.request_timeout,
    )


def _run_interactive_chat(args, store: MemoryStore) -> int:
    config = load_config(
        args.config,
        overrides=_config_overrides_from_args(args),
    )
    session_path = _session_path_for_config(args.config)

    if args.clear_session:
        SessionState.new().clear_file(session_path)
        return 0

    if args.new_session:
        SessionState.new().clear_file(session_path)

    chat_model = _model_from_config(config, config.chat_model)
    formation_model = _model_from_config(config, config.formation_model)
    resume = not args.no_resume

    while True:
        try:
            user_message = input("> ")
        except EOFError:
            flush_session_on_exit(session_path, formation_model, store)
            return 0

        stripped_message = user_message.strip()

        if stripped_message in {"/exit", "/quit"}:
            flush_session_on_exit(session_path, formation_model, store)
            return 0

        if not stripped_message:
            continue

        result = run_chat_once(
            user_message=user_message,
            config=config,
            store=store,
            session_path=session_path,
            chat_model=chat_model,
            formation_model=formation_model,
            resume=resume,
        )
        resume = True
        print(result.assistant_reply)
        if args.show_memory_trace:
            print(format_memory_trace(result.used_memories))


def _run_integrate_source(args, store: MemoryStore) -> int:
    config = load_config(args.config)
    formation_model = _model_from_config(config, config.formation_model)
    metadata = _parse_metadata(args.metadata)
    written = integrate_source_reference(
        store,
        formation_model,
        source_uri=args.source_uri,
        source_title=args.source_title,
        retrieved_at=args.retrieved_at,
        host_agent=args.host_agent,
        metadata=metadata,
    )
    _print_written_ids(written)
    return 0


def _run_integrate_evidence(args, store: MemoryStore) -> int:
    config = load_config(args.config)
    formation_model = _model_from_config(config, config.formation_model)
    metadata = _parse_metadata(args.metadata)
    written = integrate_host_evidence(
        store,
        formation_model,
        evidence=args.evidence,
        query=args.query,
        source_ids=args.source_ids or [],
        host_agent=args.host_agent,
        confidence=args.confidence,
        state=args.state,
        metadata=metadata,
    )
    _print_written_ids(written)
    return 0


def _run_integrate_answer(args, store: MemoryStore) -> int:
    config = load_config(args.config)
    formation_model = _model_from_config(config, config.formation_model)
    metadata = _parse_metadata(args.metadata)
    written = integrate_answer_trace(
        store,
        formation_model,
        query=args.query,
        answer=args.answer,
        evidence_ids=args.evidence_ids or [],
        source_ids=args.source_ids or [],
        recalled_memory_ids=args.recalled_memory_ids or [],
        host_agent=args.host_agent,
        confidence=args.confidence,
        state=args.state,
        metadata=metadata,
    )
    _print_written_ids(written)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    store = MemoryStore(args.db)

    try:
        if args.command == "init":
            store.init()
            print(f"Initialized memory database: {Path(args.db)}")
            return 0

        store.init()

        if args.command == "add":
            metadata = _parse_metadata(args.metadata)
            item = create_memory_item(
                _join_text_parts(args.content),
                memory_type=args.memory_type,
                state=args.state,
                confidence=args.confidence,
                metadata=metadata,
            )
            store.add(item)
            print(item.id)
            return 0

        if args.command == "list":
            for item in store.list(limit=args.limit):
                print(
                    f"{item.id} {item.type} {item.state} "
                    f"{item.confidence:g} {item.created_at} {_preview(item.content)}"
                )
            return 0

        if args.command == "show":
            item = store.get(args.id)
            if item is None:
                print(f"Memory not found: {args.id}", file=sys.stderr)
                return 1
            if args.as_json:
                print(json.dumps(item.to_dict(), ensure_ascii=False, sort_keys=True))
            else:
                _print_item(item)
            return 0

        if args.command == "search":
            for result in search_memories(
                store,
                _join_text_parts(args.query),
                top_k=args.top_k,
            ):
                print(
                    f"{result.item.id} score={result.score:g} "
                    f"{result.item.content}"
                )
            return 0

        if args.command == "export":
            if args.output:
                export_jsonl(store, args.output)
                print(f"Exported memory database: {Path(args.output)}")
            else:
                print(export_jsonl_text(store), end="")
            return 0

        if args.command == "integrate-source":
            return _run_integrate_source(args, store)

        if args.command == "integrate-evidence":
            return _run_integrate_evidence(args, store)

        if args.command == "integrate-answer":
            return _run_integrate_answer(args, store)

        if args.command == "chat":
            return _run_interactive_chat(args, store)

        if args.command == "ui":
            try:
                serve_ui(
                    UIState(db_path=Path(args.db), config_path=Path(args.config)),
                    host=args.host,
                    port=args.port,
                )
            except OSError as error:
                if error.errno != errno.EADDRINUSE:
                    raise
                print(
                    f"Port already in use: {args.host}:{args.port}. "
                    f"Stop the existing process or retry with --port {args.port + 1}.",
                    file=sys.stderr,
                )
                return 1
            return 0
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
