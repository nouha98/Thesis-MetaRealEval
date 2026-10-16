"""Write an isolated pilot config for one (tier, model) pair.

A pilot must never touch production results or the production LLM response
cache, and the runners give no flag for either: the only control is the YAML.
This script copies a base config and changes ONLY:

  llm.models            -> just the chosen model
  benchmark.tasks       -> the requested inclusive range, as positional indices
  project.output_dir    -> <repo>/results_test/<tier>/<model>           (absolute)
  llm.cache_dir         -> <repo>/cache/llm_responses_pilot/<tier>/<model> (absolute)

plus any other relative path in the config (benchmark.data_path, manifest_path,
rq2.paraphrase_corpus), rewritten to an absolute repo path because the pilot job
runs from its own directory (so its relative logs/ stays inside it).

Sampling, token budget, timeouts and concurrency are left exactly as in the base.

After writing, the file is reloaded through Config.from_yaml -- pydantic ignores
unknown keys silently, so a misspelt key would otherwise do nothing -- and every
override is asserted, along with the model id, the task bounds and the isolation
of both directories. A base-vs-pilot diff is printed.

Usage:
    python scripts/make_pilot_config.py --base config/tier2_realclasseval.yaml \\
        --tier tier2 --model qwen36-35b --tasks 0-2
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.config import Config  # noqa: E402

PILOT_RESULTS_ROOT = REPO_ROOT / "results_test"
PILOT_CACHE_ROOT = REPO_ROOT / "cache" / "llm_responses_pilot"

# Config paths that are relative to the repo root in the base YAMLs.
_PATH_KEYS = [("benchmark", "data_path"), ("benchmark", "manifest_path"),
              ("rq2", "paraphrase_corpus")]


class PilotConfigError(SystemExit):
    pass


def _fail(msg: str) -> None:
    raise PilotConfigError(f"ERROR: {msg}")


def parse_task_range(spec: str) -> list[int]:
    start_s, sep, end_s = spec.partition("-")
    try:
        start, end = int(start_s), int(end_s if sep else start_s)
    except ValueError:
        _fail(f"--tasks must look like START-END (inclusive), got {spec!r}")
    if start < 0 or start > end:
        _fail(f"--tasks needs 0 <= START <= END, got {spec!r}")
    return list(range(start, end + 1))


def model_in_base(base_text: str, base_raw: dict, model: str) -> str:
    """'active' | 'commented-out'; exits if the id is nowhere in the base file."""
    active = [m.get("id") for m in (base_raw.get("llm", {}).get("models") or [])]
    if model in active:
        return "active"
    if re.search(rf"^\s*#\s*-\s*id:\s*{re.escape(model)}\s*$", base_text, re.MULTILINE):
        return "commented-out"
    _fail(f"model {model!r} is not in the base config (active: {active}; "
          "commented-out entries were searched too). Refusing to invent a model id.")


def absolutise(raw: dict) -> None:
    for section, key in _PATH_KEYS:
        value = (raw.get(section) or {}).get(key)
        if value:
            p = Path(value)
            raw[section][key] = str(p if p.is_absolute() else (REPO_ROOT / p).resolve())


def flatten(d, prefix=""):
    out = {}
    if isinstance(d, dict):
        for k, v in d.items():
            out.update(flatten(v, f"{prefix}{k}."))
    else:
        out[prefix.rstrip(".")] = d
    return out


def build_pilot(base_raw: dict, tier: str, model: str, tasks: list[int]) -> tuple[dict, Path, Path]:
    raw = copy.deepcopy(base_raw)
    out_dir = (PILOT_RESULTS_ROOT / tier / model).resolve()
    cache_dir = (PILOT_CACHE_ROOT / tier / model).resolve()
    raw.setdefault("project", {})["output_dir"] = str(out_dir)
    # Carry the base entry's other fields (request_params, condition) through:
    # rebuilding it as {"id": model} would silently drop the thinking switch and
    # run the pilot at the server default.
    base_entry = next((copy.deepcopy(m) for m in (base_raw.get("llm", {}).get("models") or [])
                       if isinstance(m, dict) and m.get("id") == model), {"id": model})
    raw.setdefault("llm", {})["models"] = [base_entry]
    raw["llm"]["cache_dir"] = str(cache_dir)
    raw.setdefault("benchmark", {})["tasks"] = tasks
    absolutise(raw)
    return raw, out_dir, cache_dir


def assert_pilot(path: Path, base_path: Path, model: str, tasks: list[int],
                 out_dir: Path, cache_dir: Path, check_bounds: bool) -> None:
    pilot = Config.from_yaml(path)
    base = Config.from_yaml(base_path)

    assert pilot.model_ids() == [model], pilot.model_ids()
    # The pilot must run in the same inference condition as the base entry.
    assert pilot.llm.request_params_for(model) == base.llm.request_params_for(model), (
        pilot.llm.request_params_for(model), base.llm.request_params_for(model))
    assert pilot.benchmark.tasks == tasks, pilot.benchmark.tasks
    assert pilot.project.output_dir.resolve() == out_dir
    assert pilot.llm.cache_dir.resolve() == cache_dir
    assert pilot.project.output_dir.is_absolute() and pilot.llm.cache_dir.is_absolute()

    # Isolation: under the dedicated pilot roots, never a production location.
    assert PILOT_RESULTS_ROOT in out_dir.parents, out_dir
    assert PILOT_CACHE_ROOT in cache_dir.parents, cache_dir
    prod_cache = (REPO_ROOT / base.llm.cache_dir).resolve()
    prod_out = (REPO_ROOT / base.project.output_dir).resolve()
    assert cache_dir != prod_cache and prod_cache not in cache_dir.parents
    assert out_dir != prod_out and prod_out not in out_dir.parents

    # Nothing but the intended keys may differ from the base.
    allowed = {"project.output_dir", "llm.models", "llm.cache_dir", "benchmark.tasks"}
    allowed |= {f"{s}.{k}" for s, k in _PATH_KEYS}
    base_flat = flatten(yaml.safe_load(base_path.read_text(encoding="utf-8")) or {})
    pilot_flat = flatten(yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    for key in set(base_flat) | set(pilot_flat):
        if key.startswith("llm.models"):
            continue
        if base_flat.get(key) != pilot_flat.get(key) and key not in allowed:
            raise AssertionError(f"unexpected difference in {key!r}")
    for key in ("rq2.temperature", "rq2.n_completions", "rq2.max_tokens",
                "llm.max_concurrent_requests", "llm.requests_per_minute",
                "execution.timeout_s"):
        sec, name = key.split(".")
        assert getattr(getattr(pilot, sec), name) == getattr(getattr(base, sec), name), key

    if check_bounds:
        from meta_real_eval.benchmarks import get_benchmark
        n_tasks = len(get_benchmark(pilot).load_tasks())
        if max(tasks) >= n_tasks:
            _fail(f"task index {max(tasks)} out of bounds: benchmark has {n_tasks} task(s)")
        print(f"bounds: tasks {tasks[0]}..{tasks[-1]} within {n_tasks} available task(s)")
    else:
        print("bounds: NOT CHECKED (--skip-bounds-check); verify on the cluster")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", required=True, help="base YAML, e.g. config/tier2_realclasseval.yaml")
    ap.add_argument("--tier", required=True, choices=["tier1", "tier2"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--tasks", default="0-2", help="inclusive positional range (default 0-2)")
    ap.add_argument("--skip-bounds-check", action="store_true",
                    help="do not load the benchmark (e.g. Tier 2 manifest only exists on the cluster)")
    args = ap.parse_args(argv)

    base_path = (REPO_ROOT / args.base).resolve() if not Path(args.base).is_absolute() else Path(args.base)
    base_text = base_path.read_text(encoding="utf-8")
    base_raw = yaml.safe_load(base_text) or {}

    state = model_in_base(base_text, base_raw, args.model)
    tasks = parse_task_range(args.tasks)
    raw, out_dir, cache_dir = build_pilot(base_raw, args.tier, args.model, tasks)

    out_dir.mkdir(parents=True, exist_ok=True)
    cfg_path = out_dir / "config.yaml"
    header = (f"# PILOT config. Generated by scripts/make_pilot_config.py -- do not edit.\n"
              f"# base: {base_path.relative_to(REPO_ROOT).as_posix()}  tier: {args.tier}  "
              f"model: {args.model} ({state} in base)\n")
    cfg_path.write_text(header + yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    assert_pilot(cfg_path, base_path, args.model, tasks, out_dir, cache_dir,
                 check_bounds=not args.skip_bounds_check)

    base_flat, pilot_flat = flatten(base_raw), flatten(raw)
    print(f"wrote {cfg_path}")
    print(f"model {args.model!r} is {state} in {base_path.name}")
    print("changes vs base:")
    for key in sorted(set(base_flat) | set(pilot_flat)):
        if base_flat.get(key) != pilot_flat.get(key):
            print(f"  {key}: {base_flat.get(key)!r} -> {pilot_flat.get(key)!r}")
    print(f"config sha256: {hashlib.sha256(cfg_path.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
