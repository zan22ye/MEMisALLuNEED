from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def read_json(path: str | Path) -> object:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json_atomic(path: str | Path, value: object) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(value, fh, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp_path, target)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
