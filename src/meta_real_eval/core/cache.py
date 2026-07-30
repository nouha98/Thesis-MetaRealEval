"""Content-addressed disk cache for LLM responses."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Optional


class ResponseCache:
    """Stores LLM responses as JSON files, keyed by a SHA-256 of the request.

    Layout: cache_dir / <first-2-hex-chars> / <full-sha256>.json
    The 2-char prefix shard avoids excessively large flat directories.
    Writes are atomic (write to .tmp then rename) so a crash during write
    never leaves a corrupt entry.
    """

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def key(self, model: str, messages: list[dict], **params) -> str:
        blob = json.dumps(
            {"model": model, "messages": messages, **params},
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def _path(self, key: str) -> Path:
        return self._dir / key[:2] / f"{key}.json"

    def get(self, key: str) -> Optional[dict]:
        path = self._path(key)
        if path.exists():
            try:
                return json.loads(path.read_text())
            except json.JSONDecodeError:
                path.unlink(missing_ok=True)
        return None

    def put(self, key: str, data: dict) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data))
        tmp.rename(path)
