"""Shared helpers for the extension scripts (plan rev. 9): task loading, the frozen Tier 2
inputs, and fault-record collection. Read-only on every historical result."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402
from meta_real_eval.core.provenance import verify_pins  # noqa: E402

PROTOCOL_DIR = REPO / "config" / "extensions_protocol"
DEPENDENCY_SCAN = REPO / "data" / "realclasseval" / "dependency_scan.json"


def load_ext_config(path: Path) -> Config:
    cfg = Config.from_yaml(path)
    if cfg.extensions is None:
        raise SystemExit(f"ERROR: {path} has no `extensions` section")
    return cfg


def load_tasks(cfg: Config, ungated: bool) -> tuple[dict, bool]:
    """{label: Task} for the accepted Tier 2 tasks, and whether the gate manifest was used.

    With the manifest (freia) tasks carry gate verdicts and are authoritative. Without it,
    ``--ungated`` reads the corpus and keeps the 375 labels present in the frozen baseline;
    results are then marked non-authoritative (gate-excluded P scenarios cannot be removed)."""
    bench = get_benchmark(cfg)
    try:
        tasks = bench.load_tasks()
        return {t.label: t for t in tasks}, True
    except Exception as exc:
        if not ungated:
            raise SystemExit(f"ERROR: {type(exc).__name__}: {exc}\n"
                             "       run on freia (with the gate manifest) or pass --ungated for a "
                             "non-authoritative local run") from exc
    accepted = {p.name for p in (Path(cfg.extensions.baseline_scores) / "rq2" / "evaluate").iterdir() if p.is_dir()}
    return {t.label: t for t in bench.corpus_tasks() if t.label in accepted}, False


def check_development_mapping(cfg: Config, tasks: dict, gated: bool) -> Optional[list[str]]:
    """With the manifest, the pinned development indices must map to the pinned labels."""
    ext = cfg.extensions
    if not gated or not ext.development_task_indices:
        return None
    by_index = {t.task_index: lab for lab, t in tasks.items()}
    bad = [f"{i}->{by_index.get(i)} (pinned {lab})" for i, lab in zip(ext.development_task_indices, ext.development_tasks)
           if by_index.get(i) != lab]
    if bad:
        raise SystemExit(f"ERROR: development task index/label mapping differs: {bad}")
    return []


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def collect_fault_records(bench, task, baseline: Path) -> list[dict]:
    """Every stored mutant record of a task (operators from Stage 0, whole-source LLM mutants from
    RQ1), with runnable code (LLM mutants go through the adapter's repair, as RQ1 evaluate did)
    and provenance. Records whose code cannot be repaired keep their raw code, flagged invalid."""
    recs: list[dict] = []
    for m in read_json(baseline / "stage0" / task.label / "mutants.json", []):
        recs.append({"task": task.label, "record_id": m["mutant_id"], "source": "operator",
                     "operator": m["operator"], "description": m.get("description"), "method": m.get("method"),
                     "code": m["code"], "runnable": True})
    meta = read_json(baseline / "rq1" / "generate" / task.label / "generation_meta.json", {})
    for m in read_json(baseline / "rq1" / "generate" / task.label / "llm_mutants.json", []):
        model = m.get("source_model") or m["mutant_id"].split("-", 1)[1].rsplit("-", 1)[0]
        attempts = (meta.get(model) or {}).get("attempts") or [{}]
        repaired = bench.repair_mutant(task, m["code"])
        recs.append({"task": task.label, "record_id": m["mutant_id"], "source": "llm_whole", "model": model,
                     "attempt": attempts[-1].get("attempt"), "fault_hint": attempts[-1].get("fault_hint"),
                     "prompt_sha256": attempts[-1].get("prompt_sha256"),
                     "code": repaired if repaired is not None else m["code"], "runnable": repaired is not None})
    return recs


def historical_status(task_label: str, baseline: Path) -> dict:
    """record_id -> {"equivalence": reason, "killed": bool|None} from the stored Stage 0 / RQ1 files."""
    out: dict = {}
    for e in read_json(baseline / "stage0" / task_label / "equiv_filter.json", []):
        out.setdefault(e["mutant_id"], {})["equivalence"] = e["reason"]
    for e in read_json(baseline / "rq1" / "evaluate" / task_label / "llm_equiv_filter.json", []):
        out.setdefault(e["mutant_id"], {})["equivalence"] = e["reason"]
    for k in read_json(baseline / "rq1" / "evaluate" / task_label / "kill_matrix.json", []):
        out.setdefault(k["mutant_id"], {})["killed"] = k["is_killed"]
    return out


def pins_ok(cfg: Config) -> dict:
    return verify_pins(cfg.extensions.pins)
