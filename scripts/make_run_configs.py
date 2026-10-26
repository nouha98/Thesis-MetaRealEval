"""Split the Tier 2 config into one config per serving group, plus the combined one.

    innkube           gemma4-31b-it                  CPU job against the Innkube gateway
    vllm-qwen38       qwen38-27b                     one vLLM GPU job (the gateway's ~9 min
                                                     request limit cuts its thinking off)
    vllm-qwen3-next   qwen3-next-80b-a3b-instruct    one vLLM GPU job
    vllm-qwen36       qwen36-35b                     one vLLM GPU job
    combined          all models                     merge target; Stage 0 and all
                                                     evaluation run here

Each group generates into its own directory (one GPU job serves one model, so
parallel jobs never write the same completions.json); merge_generation_runs.py
then builds the combined directory. Only these keys differ from the base,
which is asserted after writing:

    project.output_dir   results_tier2_runs/<label>/<group>
    llm.cache_dir        cache/llm_responses_tier2_runs/<label>/<group>
    llm.models           the group's models (entries copied verbatim)
    llm.max_concurrent_requests / requests_per_minute   vLLM groups only: a
                         dedicated server batches many requests (client limits,
                         not part of the protocol)
    benchmark.tasks      only with --tasks (a pilot; needs --label)

Paths stay repo-relative: run everything from the repo root.

    python scripts/make_run_configs.py                       # label "full"
    python scripts/make_run_configs.py --tasks 1,2,8,10,15,187,188,189,192,224 --label pilot
"""

from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from meta_real_eval.core.config import Config  # noqa: E402
from make_pilot_config import flatten  # noqa: E402

BASE = Path("config/tier2_realclasseval.yaml")
OUT_DIR = Path("config/tier2_runs")
GROUPS = {
    "innkube": ["gemma4-31b-it"],
    "vllm-qwen38": ["qwen38-27b"],
    "vllm-qwen3-next": ["qwen3-next-80b-a3b-instruct"],
    "vllm-qwen36": ["qwen36-35b"],
}
COMBINED = "combined"
VLLM_CLIENT = {"max_concurrent_requests": 16, "requests_per_minute": 600}


def parse_tasks(spec: str | None) -> list[int] | None:
    """'1,2,8' or '0-9' or a mix; None -> the base's population."""
    if not spec:
        return None
    out: list[int] = []
    for item in spec.split(","):
        a, sep, b = item.strip().partition("-")
        lo, hi = int(a), int(b if sep else a)
        if lo < 0 or lo > hi:
            raise SystemExit(f"ERROR: --tasks item {item!r} needs 0 <= START <= END")
        out.extend(range(lo, hi + 1))
    if len(set(out)) != len(out):
        raise SystemExit(f"ERROR: --tasks repeats an index: {spec!r}")
    return out


def build(base_raw: dict, group: str, label: str, tasks: list[int] | None) -> dict:
    models = base_raw["llm"]["models"]
    wanted = [m["id"] for m in models] if group == COMBINED else GROUPS[group]
    raw = copy.deepcopy(base_raw)
    raw["project"]["output_dir"] = f"results_tier2_runs/{label}/{group}"
    raw["llm"]["cache_dir"] = f"cache/llm_responses_tier2_runs/{label}/{group}"
    raw["llm"]["models"] = [copy.deepcopy(m) for m in models if m["id"] in wanted]
    if group.startswith("vllm-"):
        raw["llm"].update(VLLM_CLIENT)
    if tasks is not None:
        raw["benchmark"]["tasks"] = tasks
    return raw


def check(base_raw: dict, written: dict[str, dict], tasks: list[int] | None) -> None:
    base_ids = [m["id"] for m in base_raw["llm"]["models"]]
    grouped = [mid for ids in GROUPS.values() for mid in ids]
    assert sorted(grouped) == sorted(base_ids), f"groups {grouped} != base models {base_ids}"
    assert len(grouped) == len(set(grouped)), "a model is in two groups"
    allowed = {"project.output_dir", "llm.cache_dir", "llm.max_concurrent_requests",
               "llm.requests_per_minute"} | ({"benchmark.tasks"} if tasks is not None else set())
    base_flat = flatten(base_raw)
    dirs = set()
    for group, raw in written.items():
        new_flat = flatten(raw)
        for key in set(base_flat) | set(new_flat):
            if key == "llm.models":
                continue
            if base_flat.get(key) != new_flat.get(key) and key not in allowed:
                raise AssertionError(f"{group}: unexpected difference from the base in {key!r}")
        for m in raw["llm"]["models"]:
            assert m == next(b for b in base_raw["llm"]["models"] if b["id"] == m["id"]), m["id"]
        dirs |= {raw["project"]["output_dir"], raw["llm"]["cache_dir"]}
    assert len(dirs) == 2 * len(written), "two groups share an output or cache dir"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--base", type=Path, default=BASE)
    ap.add_argument("--tasks", default=None, help="positional indices: '1,2,8' or '0-9'")
    ap.add_argument("--label", default="full", help="'full', or e.g. 'pilot' with --tasks")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = ap.parse_args(argv)

    tasks = parse_tasks(args.tasks)
    if (tasks is None) != (args.label == "full"):
        raise SystemExit("ERROR: --tasks needs its own --label (not 'full'), and 'full' takes no --tasks")
    base_path = args.base if args.base.is_absolute() else REPO_ROOT / args.base
    base_raw = yaml.safe_load(base_path.read_text(encoding="utf-8"))

    written = {g: build(base_raw, g, args.label, tasks) for g in [*GROUPS, COMBINED]}
    check(base_raw, written, tasks)
    out_dir = args.out_dir if args.out_dir.is_absolute() else REPO_ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    for group, raw in written.items():
        path = out_dir / f"{args.label}_{group}.yaml"
        path.write_text(
            f"# GENERATED by scripts/make_run_configs.py from {args.base.as_posix()} -- do not\n"
            "# edit; change the base and regenerate. Run from the repo root.\n"
            + yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
        cfg = Config.from_yaml(path)               # validates (incl. retry_policy needs profiles)
        print(f"wrote {path.relative_to(REPO_ROOT).as_posix() if path.is_relative_to(REPO_ROOT) else path}: "
              f"models={cfg.model_ids()} out={cfg.project.output_dir.as_posix()}")


if __name__ == "__main__":
    main()
