#!/usr/bin/env python
"""M1(c): generation audit for stored RQ2 completions.

Two tables:

1. D7 extraction (RealClassEval only). Per (relation, model), counts how each
   completion classifies under the D7 extraction (fenced / raw / trimmed /
   failed). ``trimmed`` means the raw output yielded a class only after it was
   cut back to the part that parses, the usual signature of a truncated
   completion; ``failed`` means no top-level class was found.

2. Request telemetry, from generation_meta.json (runs made with the inference
   protocol). Per model: cell status (ok / transport_failure / context_overflow
   / generation_failed), truncation rate (finish_reason=length), unusable
   dispositions, completion and reasoning tokens per request, reasoning-field
   characters per choice, and client-observed latency (p50/p95, successful
   attempt and total including transport retries).

   Missing telemetry is counted as unavailable, never as 0: usage is reported
   per request (never divided into per-choice tokens), reasoning tokens only
   when the API reports them, and an empty reasoning field never means
   "thinking off". Latency is comparable only within one model on one
   endpoint.

    .venv/bin/python scripts/audit_rq2_generation.py --config config/generated/tier2/native_pilot_combined.yaml
"""

from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.checkpoint import read_json, task_dir  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(round(q * (len(s) - 1))))]


def _request_meta(cell: dict) -> dict | None:
    """The meta of the request that produced the stored completions."""
    if "request" in cell:                       # transport_only
        return cell["request"]
    for attempt in reversed(cell.get("attempts") or []):   # legacy: last successful attempt
        if "request" in attempt:
            return attempt["request"]
    return None


def _records(cell: dict) -> list[dict]:
    if "records" in cell:
        return cell["records"] or []
    for attempt in reversed(cell.get("attempts") or []):
        if "records" in attempt:
            return attempt["records"] or []
    return []


def telemetry(cells_by_model: dict[str, list[dict]]) -> list[dict]:
    rows = []
    for model, cells in sorted(cells_by_model.items()):
        status = collections.Counter(c.get("status", "unknown") for c in cells)
        records = [r for c in cells for r in _records(c)]
        finish = collections.Counter(r.get("finish_reason", "unknown") for r in records)
        disp = collections.Counter(r.get("disposition", "unknown") for r in records)
        metas = [m for m in (_request_meta(c) for c in cells) if m]
        tokens = [m["usage"]["completion_tokens"] for m in metas
                  if (m.get("usage") or {}).get("completion_tokens") is not None]
        reasoning_tokens = [m["reasoning_tokens"] for m in metas if m.get("reasoning_tokens") is not None]
        rchars = [ch["reasoning_field_chars"] for m in metas for ch in (m.get("choices") or [])
                  if ch.get("reasoning_field_chars") is not None]
        succ = [m["success_latency_s"] for m in metas if m.get("success_latency_s") is not None]
        total = [m["total_latency_s"] for m in metas if m.get("total_latency_s") is not None]
        n_choices = len(records)
        rows.append({
            "model": model,
            "cells": len(cells),
            "status": dict(status),
            "choices": n_choices,
            "truncation_rate": finish["length"] / n_choices if n_choices else None,
            "finish_reasons": dict(finish),
            "unusable_rate": (sum(v for k, v in disp.items() if k.startswith("unusable")) / n_choices
                              if n_choices else None),
            "dispositions": dict(disp),
            "completion_tokens_per_request": {
                "median": statistics.median(tokens) if tokens else None,
                "p95": _quantile(tokens, 0.95), "max": max(tokens) if tokens else None,
                "unavailable": len(metas) - len(tokens)},
            "reasoning_tokens_per_request": {
                "median": statistics.median(reasoning_tokens) if reasoning_tokens else None,
                "unavailable": len(metas) - len(reasoning_tokens)},
            "reasoning_field_chars_per_choice": {
                "median": statistics.median(rchars) if rchars else None,
                "unavailable": sum(len(m.get("choices") or []) for m in metas) - len(rchars)},
            "latency_s": {"success_p50": _quantile(succ, 0.5), "success_p95": _quantile(succ, 0.95),
                          "total_p50": _quantile(total, 0.5), "total_p95": _quantile(total, 0.95),
                          "requests_with_transport_retries":
                              sum(1 for m in metas if len(m.get("attempts") or []) > 1),
                          "note": "client-observed; within-model comparison only"},
            "requests_without_meta": len(cells) - len(metas),
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", default="config/tier2_m1_pilot.yaml")
    args = parser.parse_args()

    cfg = Config.from_yaml(args.config)
    tasks = get_benchmark(cfg).load_tasks(cfg.benchmark.tasks)
    d7 = cfg.benchmark.name == "realclasseval"
    if d7:
        from meta_real_eval.benchmarks.realclasseval import build_solution_with_report

    cells: dict[tuple[str, str], collections.Counter] = collections.defaultdict(collections.Counter)
    meta_cells: dict[str, list[dict]] = collections.defaultdict(list)
    missing_tasks = []
    for task in tasks:
        out = task_dir(cfg, "rq2", task.label, phase="generate")
        try:
            data = read_json(out, "completions.json")
        except FileNotFoundError:
            missing_tasks.append(task.task_id)
            continue
        if (out / "generation_meta.json").is_file():
            for _relation, by_model in read_json(out, "generation_meta.json").items():
                for model, cell in by_model.items():
                    meta_cells[model].append(cell)
        if not d7:
            continue
        for relation, by_model in data.items():
            for model, completions in by_model.items():
                cell = cells[(relation, model)]
                if not completions:
                    cell["empty_cell"] += 1
                    continue
                for completion in completions:
                    _, report = build_solution_with_report(completion, task.prompt, task.target)
                    cell["completions"] += 1
                    cell[report.extraction] += 1
                    cell["reattached_imports"] += len(report.imports_reattached)

    rows = []
    if d7:
        print(f"{'relation':18s} {'model':30s} {'n':>5s} {'fenced':>7s} {'raw':>5s} "
              f"{'trimmed':>8s} {'failed':>7s} {'empty':>6s} {'reattach':>9s}")
        for (relation, model), c in sorted(cells.items()):
            n = c["completions"]
            pct = lambda k: f"{c[k] / n:.1%}" if n else "-"  # noqa: E731
            print(f"{relation:18s} {model:30s} {n:5d} {pct('fenced'):>7s} {pct('raw'):>5s} "
                  f"{pct('trimmed'):>8s} {pct('failed'):>7s} {c['empty_cell']:6d} {c['reattached_imports']:9d}")
            rows.append({"relation": relation, "model": model, "n": n, "fenced": c["fenced"],
                         "raw": c["raw"], "trimmed": c["trimmed"], "failed": c["failed"],
                         "empty_cell": c["empty_cell"], "reattached_imports": c["reattached_imports"]})
    if missing_tasks:
        print(f"\nno completions.json for {len(missing_tasks)} task(s): {missing_tasks}")

    out_dir = Path(cfg.project.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if d7:
        (out_dir / "rq2_generation_audit.json").write_text(json.dumps(rows, indent=1) + "\n",
                                                           encoding="utf-8")
        print(f"\nwritten -> {out_dir / 'rq2_generation_audit.json'}")

    if meta_cells:
        tel = telemetry(meta_cells)
        print("\nrequest telemetry (per model; latency comparable within a model only):")
        for r in tel:
            tr = "-" if r["truncation_rate"] is None else f"{r['truncation_rate']:.1%}"
            un = "-" if r["unusable_rate"] is None else f"{r['unusable_rate']:.1%}"
            ct = r["completion_tokens_per_request"]
            lat = r["latency_s"]
            print(f"  {r['model']:30s} cells={r['cells']:5d} status={r['status']} "
                  f"trunc={tr} unusable={un} tokens/request med={ct['median']} p95={ct['p95']} "
                  f"(unavailable {ct['unavailable']}) latency p50/p95={lat['success_p50']}/"
                  f"{lat['success_p95']}s total p95={lat['total_p95']}s")
        (out_dir / "rq2_generation_telemetry.json").write_text(json.dumps(tel, indent=1) + "\n",
                                                               encoding="utf-8")
        print(f"written -> {out_dir / 'rq2_generation_telemetry.json'}")
    else:
        print("\nno generation_meta.json found: runs made before the inference protocol "
              "carry no request telemetry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
