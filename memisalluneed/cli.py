from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from memisalluneed.config import DEFAULT_CONFIG_PATH
from memisalluneed.export import export_jsonl, export_jsonl_text
from memisalluneed.schema import create_memory_item
from memisalluneed.search import search_memories
from memisalluneed.store import DEFAULT_DB_PATH, MemoryStore


def _add_db_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="Path to the SQLite memory database.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mem")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a memory database.")
    _add_db_argument(init_parser)

    add_parser = subparsers.add_parser("add", help="Add a memory item.")
    add_parser.add_argument("content")
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
    search_parser.add_argument("query")
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
    chat_parser.add_argument("--new-session", action="store_true")
    chat_parser.add_argument("--clear-session", action="store_true")
    chat_parser.add_argument("--no-resume", action="store_true")

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
                args.content,
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
            for result in search_memories(store, args.query, top_k=args.top_k):
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
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
