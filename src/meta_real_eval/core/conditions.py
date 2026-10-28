"""Record, and guard, the inference settings each model in a results dir ran under.

``completions.json`` is keyed by model id alone, so nothing in it says which
sampling parameters or request fields produced a completion. Resuming a run
with a different config would silently interleave incomparable samples under
one id. ``record_llm_conditions`` writes ``<output_dir>/llm_conditions.json``
and refuses to proceed on a conflict:

  settings  the run's protocol: benchmark and task population, relations, n,
            token budgets, retry and evaluation policy. Paths, model lists and
            endpoints are excluded (they differ between the gateway job and a
            vLLM job of the same run). The merge compares it across sources.
  models    per model: sampling + request_params, compared on resume.
  sessions  one entry per run: phase, time, git commit, host, endpoint --
            provenance only, never compared (a vLLM port changes per job).

A directory with no manifest (every run made before this existed) is not
guessed at: its results ran under the server defaults of the day.
"""

from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config

MANIFEST_NAME = "llm_conditions.json"
FORMAT = 2
_REPO_ROOT = Path(__file__).resolve().parents[3]


class ConditionMismatch(SystemExit):
    pass


def _file_sha256(path: Path | None) -> str | None:
    if path is None or not Path(path).is_file():
        return None
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def protocol_settings(cfg: Config) -> dict[str, Any]:
    """What makes two runs comparable. Excludes ``rq3.divergence_threshold``,
    an output of calibration written into the config later.

    Settings added after runs already existed appear only when non-default, so
    a directory written before them (the 2026-10 pilot, every Tier 1 run) still
    compares equal and can be resumed or re-evaluated."""
    b = cfg.benchmark
    r = cfg.rq2
    later = {k: v for k, v, default in (
        ("request_seeds", r.request_seeds, False),
        ("control_marker_models", r.control_marker_models, None),
        ("ranking_score", r.ranking_score, "pass@1"),
    ) if v != default}
    return {
        **later,
        "project_seed": cfg.project.seed,
        "benchmark": {"name": b.name, "tasks": b.tasks, "splits": b.splits,
                      "docstring_variant": b.docstring_variant,
                      "data_sha256": _file_sha256(b.data_path),
                      "manifest_sha256": _file_sha256(b.manifest_path)},
        "relations": cfg.rq2.relations,
        "corpus_sha256": cfg.rq2.corpus_sha256,
        "n_completions": cfg.rq2.n_completions,
        "max_tokens": {"rq1": cfg.rq1.max_tokens, "rq2": cfg.rq2.max_tokens},
        "fallback_temperature": cfg.rq2.temperature,
        "retry_policy": cfg.rq2.retry_policy,
        "sbc_model": cfg.rq3.sbc_model,
        "evaluation": {"timeout_s": cfg.execution.timeout_s, "stage0": cfg.stage0.model_dump(),
                       "rq1_operators": cfg.rq1.operators,
                       "rq3_n_shared_inputs": cfg.rq3.n_shared_inputs,
                       "rq3_variant_sample_per_family": cfg.rq3.variant_sample_per_family,
                       "rq4_degradation_levels": cfg.rq4.degradation_levels},
    }


def current_models(cfg: Config) -> dict[str, dict[str, Any]]:
    return {m.id: m.effective_condition() for m in cfg.llm.models}


def _git_commit() -> str | None:
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, capture_output=True,
                              text=True, timeout=10, check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               cwd=_REPO_ROOT, capture_output=True, text=True, timeout=10,
                               check=True).stdout.strip()
        return head + ("-dirty" if dirty else "")
    except (OSError, subprocess.SubprocessError):
        return None


def _mismatch(out_dir: Path, what: str) -> ConditionMismatch:
    return ConditionMismatch(
        f"ERROR: {out_dir}: {what}. One results directory holds one configuration "
        "per model: use a separate output_dir and cache_dir for the other one."
    )


def record_llm_conditions(cfg: Config, phase: str | None = None) -> Path | None:
    """Write/merge the manifest; abort on a conflicting configuration. None in mock mode."""
    if cfg.project.mock:
        return None
    out_dir = Path(cfg.project.output_dir)
    path = out_dir / MANIFEST_NAME
    settings = json.loads(json.dumps(protocol_settings(cfg)))     # as it reads back from JSON
    current = current_models(cfg)

    previous: dict[str, Any] = {}
    if path.is_file():
        previous = json.loads(path.read_text(encoding="utf-8"))
        if previous.get("format") != FORMAT:
            raise _mismatch(out_dir, f"{MANIFEST_NAME} is in an older format")
        for model_id, now in current.items():
            before = previous.get("models", {}).get(model_id)
            if before is not None and before != now:
                raise _mismatch(out_dir, f"{model_id!r} was run with {before!r} but the "
                                         f"config now says {now!r}")
        if previous.get("settings") != settings:
            raise _mismatch(out_dir, "protocol settings (benchmark, tasks, relations, n, "
                                     "budgets, retry or evaluation policy) differ from the "
                                     "first run in this directory")

    session = {
        "phase": phase,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_commit": _git_commit(),
        "host": socket.gethostname(),
        # Where the requests went. The URL is not a secret; the key is never read here.
        "endpoint": os.environ.get("INNKUBE_BASE_URL", "").rstrip("/") or None,
        "models": sorted(current),
    }
    payload = {
        "format": FORMAT,
        "settings": settings,
        "models": {**previous.get("models", {}), **current},
        "sessions": [*previous.get("sessions", []), session],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)
    return path
