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
