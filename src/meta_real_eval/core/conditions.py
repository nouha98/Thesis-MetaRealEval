"""Record, and guard, the inference condition each model in a results dir ran under.

``completions.json`` is keyed by model id alone, so nothing in it says whether a
model ran with thinking on or off. Mixing two conditions in one output directory
(say, resuming a thinking-off run with a thinking-on config) would silently
interleave incomparable samples under one id. ``record_llm_conditions`` writes
``<output_dir>/llm_conditions.json`` and refuses to proceed if a model's
``request_params`` differ from what that directory already recorded.

A directory with no manifest (every run made before this existed) is not
guessed at: its results ran under the server defaults of the day, which is not
the same thing as ``request_params == {}`` being verified.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import Config

MANIFEST_NAME = "llm_conditions.json"


class ConditionMismatch(SystemExit):
    pass


def current_conditions(cfg: Config) -> dict[str, dict[str, Any]]:
    return {
        m.id: {"condition": m.condition, "request_params": m.request_params}
        for m in cfg.llm.models
    }


def record_llm_conditions(cfg: Config) -> Path | None:
    """Write/merge the manifest; abort on a conflicting condition. None in mock mode."""
    if cfg.project.mock:
        return None
    out_dir = Path(cfg.project.output_dir)
    path = out_dir / MANIFEST_NAME
    current = current_conditions(cfg)

    previous: dict[str, Any] = {}
    if path.is_file():
        previous = json.loads(path.read_text(encoding="utf-8")).get("models", {})
        for model_id, now in current.items():
            before = previous.get(model_id)
            if before is not None and before.get("request_params") != now["request_params"]:
                raise ConditionMismatch(
                    f"ERROR: {model_id!r} in {out_dir} was run with request_params "
                    f"{before.get('request_params')!r} (condition {before.get('condition')!r}) "
                    f"but the config now says {now['request_params']!r} "
                    f"(condition {now['condition']!r}). One results directory holds one "
                    "condition per model: use a separate output_dir and cache_dir for the "
                    "other condition."
                )

    merged = {**previous, **current}
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        # Where the requests went. The URL is not a secret; the key is never read here.
        "endpoint": os.environ.get("INNKUBE_BASE_URL", "").rstrip("/") or None,
        "models": merged,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path
