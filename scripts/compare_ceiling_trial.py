#!/usr/bin/env python
"""Compare an RQ2 output-ceiling trial with the run it re-generates, cell by cell.

For one model, on every (task, relation) cell the trial generated, prints both
runs side by side: length-truncated choices, unusable choices (cut off while
still reasoning, no answer), completion tokens, and -- when both runs are
evaluated -- mean graded score and pass@1. Then the totals against the decision
rule written before the trial (S4): truncation at most half the baseline's,
fewer unusable choices, and the cost.

The trial reuses the baseline's seeds, but vLLM batching is not bit-exact, so
the runs are separately sampled: read the comparison as unpaired. Scores are
reported, never part of the decision.

Cost: the trial's extra completion tokens on these cells, as a share of the
baseline's completion tokens for this model over ALL its tasks -- the increase a
run with the baseline's task mix would see. An estimate, not a measurement.

    .venv/bin/python scripts/compare_ceiling_trial.py \
        --baseline config/tier2_runs/pilot2_combined.yaml \
        --trial config/tier2_runs/ceil65k_vllm-qwen38.yaml --model qwen38-27b
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.benchmarks import get_benchmark  # noqa: E402
from meta_real_eval.core.checkpoint import read_json, task_dir  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from audit_rq2_generation import _records, _request_meta  # noqa: E402


def _json_or_none(path: Path, name: str):
    try:
        return read_json(path, name)
    except FileNotFoundError:
        return None


def cell_stats(cfg: Config, label: str, relation: str, model: str) -> dict | None:
    meta = _json_or_none(task_dir(cfg, "rq2", label, phase="generate"), "generation_meta.json")
    cell = (meta or {}).get(relation, {}).get(model)
    if cell is None:
        return None
    records = _records(cell)
    usage = (_request_meta(cell) or {}).get("usage") or {}
    rates = _json_or_none(task_dir(cfg, "rq2", label, phase="evaluate"), "pass_rates.json")
    scored = (rates or {}).get(relation, {}).get(model) or {}
    return {"n": len(records),
            "length": sum(r.get("finish_reason") == "length" for r in records),
            "unusable": sum(str(r.get("disposition", "")).startswith("unusable") for r in records),
            "tokens": usage.get("completion_tokens"),
            "graded": scored.get("mean_primary"), "pass1": scored.get("pass@1")}


def model_tokens(cfg: Config, model: str) -> int:
    total = 0
    for task in get_benchmark(cfg).load_tasks(cfg.benchmark.tasks):
        meta = _json_or_none(task_dir(cfg, "rq2", task.label, phase="generate"), "generation_meta.json")
        for by_model in (meta or {}).values():
            if model in by_model:
                total += ((_request_meta(by_model[model]) or {}).get("usage") or {}).get(
                    "completion_tokens") or 0
    return total


def _fmt(v, spec: str = "") -> str:
    return "-" if v is None else format(v, spec)


def _mean(values: list) -> float | None:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--trial", required=True)
    ap.add_argument("--model", required=True)
    args = ap.parse_args()

    base_cfg, trial_cfg = Config.from_yaml(args.baseline), Config.from_yaml(args.trial)
    print(f"ceilings: baseline rq2.max_tokens={base_cfg.rq2.max_tokens}  "
          f"trial rq2.max_tokens={trial_cfg.rq2.max_tokens}  model={args.model}\n")
    print(f"{'task':22s} {'relation':18s} {'trunc b/t':>10s} {'unusable b/t':>13s} "
          f"{'tokens b/t (k)':>16s} {'graded b/t':>12s} {'pass@1 b/t':>12s}")

    pairs = []
    for task in get_benchmark(trial_cfg).load_tasks(trial_cfg.benchmark.tasks):
        meta = _json_or_none(task_dir(trial_cfg, "rq2", task.label, phase="generate"),
                             "generation_meta.json") or {}
        for relation in meta:
            t = cell_stats(trial_cfg, task.label, relation, args.model)
            b = cell_stats(base_cfg, task.label, relation, args.model)
            if t is None:
                continue
            if b is None:
                print(f"{task.label:22s} {relation:18s} not in the baseline -- skipped")
                continue
            pairs.append((b, t))
            k = lambda x: None if x is None else x / 1000  # noqa: E731
            print(f"{task.label:22s} {relation:18s} {b['length']:>4d}/{t['length']:<5d} "
                  f"{b['unusable']:>6d}/{t['unusable']:<6d} "
                  f"{_fmt(k(b['tokens']), '.0f'):>7s}/{_fmt(k(t['tokens']), '.0f'):<8s} "
                  f"{_fmt(b['graded'], '.3f'):>5s}/{_fmt(t['graded'], '.3f'):<6s} "
                  f"{_fmt(b['pass1'], '.2f'):>5s}/{_fmt(t['pass1'], '.2f'):<6s}")

    if not pairs:
        print("no cell found in both runs")
        return 1
    tot = lambda run, key: sum(p[run][key] or 0 for p in pairs)  # noqa: E731
    n = tot(0, "n")
    b_len, t_len = tot(0, "length"), tot(1, "length")
    b_un, t_un = tot(0, "unusable"), tot(1, "unusable")
    extra = tot(1, "tokens") - tot(0, "tokens")
    all_base = model_tokens(base_cfg, args.model)

    print(f"\n{len(pairs)} cells, {n} choices per run")
    print(f"  truncated (finish=length) : baseline {b_len}/{n}  trial {t_len}/{n}")
    print(f"  unusable (no answer)      : baseline {b_un}/{n}  trial {t_un}/{n}")
    print(f"  completion tokens         : baseline {tot(0, 'tokens'):,}  trial {tot(1, 'tokens'):,}  "
          f"(extra {extra:+,})")
    if all_base:
        print(f"  cost estimate             : extra tokens = {extra / all_base:+.1%} of the baseline's "
              f"{args.model} tokens over all {len(get_benchmark(base_cfg).load_tasks(base_cfg.benchmark.tasks))} "
              f"tasks ({all_base:,})")
    bg, tg = _mean([p[0]["graded"] for p in pairs]), _mean([p[1]["graded"] for p in pairs])
    bp, tp = _mean([p[0]["pass1"] for p in pairs]), _mean([p[1]["pass1"] for p in pairs])
    print(f"  mean graded / pass@1      : baseline {_fmt(bg, '.3f')} / {_fmt(bp, '.3f')}  "
          f"trial {_fmt(tg, '.3f')} / {_fmt(tp, '.3f')}  (descriptive only; unpaired)")

    print("\ndecision rule (written before the trial):")
    print(f"  1. truncated <= half the baseline ({b_len // 2}) : "
          f"{'YES' if t_len <= b_len // 2 else 'NO'} ({t_len})")
    print(f"  2. fewer unusable than the baseline ({b_un})    : "
          f"{'YES' if t_un < b_un else 'NO'} ({t_un})")
    print("  3. projected full run fits the GPU budget     : apply the cost estimate to the "
          "full-run projection")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
