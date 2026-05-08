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
