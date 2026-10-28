"""Merge per-endpoint generation runs into one combined results directory.

Generation runs once per serving group (the gateway models in a CPU job, each
self-hosted vLLM model in a GPU job); everything downstream (Stage 0, RQ1-RQ4
evaluation, rankings, tau_div) runs ONCE over all models together. This script
is the step in between, and it is a scientific-integrity gate, not a file copy:
it refuses unless

  * every source ran the same protocol settings as the combined config
    (benchmark, tasks, relations, n, budgets, retry and evaluation policy), and
    every source model ran exactly the sampling / request_params the combined
    config lists for it;
  * the source model sets are disjoint and together are exactly the combined
    config's models;
  * coverage is exact: every task x relation x model cell exists with exactly
    n completions -- or, with --allow-failures, is an explicit transport
    failure documented by the generator (never a silently missing cell);
    likewise for RQ1 (which marks a task done even when some models failed);
  * the logical task prompt (before the per-model control marker) is identical
    across every model and source, for every task x relation (RQ2) and every
    task x attempt (RQ1);
  * the target is empty, or already holds exactly what would be written.

Sources are only read. The target gets completions.json / llm_mutants.json and
their generation_meta.json (models in combined-config order, lineage kept), done
markers (so the combined config's generate phases never call an endpoint), the
union llm_conditions.json, and merge_provenance.json with each source's
provenance (models, serving info, file sha256s).

Usage:
    python scripts/merge_generation_runs.py results_tier2_runs/full/innkube \\
        results_tier2_runs/full/vllm-qwen38 results_tier2_runs/full/vllm-qwen36 \\
        --config config/tier2_runs/full_combined.yaml [--phases rq1,rq2]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.core.checkpoint import mark_done, task_dir, write_json  # noqa: E402
from meta_real_eval.core.conditions import MANIFEST_NAME, protocol_settings  # noqa: E402
from meta_real_eval.core.config import Config  # noqa: E402

PHASES = ("rq1", "rq2")
# Cell statuses the generator writes for a cell with no model output. Only these
# may be carried through (with --allow-failures); anything else is a defect.
FAILURE_STATUSES = ("transport_failure", "context_overflow")


class MergeError(SystemExit):
    pass


class _Problems:
    """Collect every refusal reason before failing, so one run lists them all."""

    def __init__(self) -> None:
        self.items: list[str] = []

    def add(self, msg: str) -> None:
        self.items.append(msg)

    def raise_if_any(self, header: str) -> None:
        if self.items:
            shown = "\n  - ".join(self.items[:50])
            more = f"\n  ... and {len(self.items) - 50} more" if len(self.items) > 50 else ""
            raise MergeError(f"ERROR: {header}:\n  - {shown}{more}")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_commit() -> str | None:
    from meta_real_eval.core.conditions import _git_commit as commit
    return commit()


# ---------------------------------------------------------------------------
# Identity checks
# ---------------------------------------------------------------------------

def load_manifest(src: Path) -> dict:
    path = src / MANIFEST_NAME
    if not path.is_file():
        raise MergeError(f"ERROR: {src} has no {MANIFEST_NAME}; not a generation run of this protocol")
    m = _read_json(path)
    if m.get("format") != 2:
        raise MergeError(f"ERROR: {path} is an old-format manifest; regenerate that run")
    return m


def check_identities(cfg: Config, sources: dict[Path, dict], problems: _Problems) -> None:
    want_settings = json.loads(json.dumps(protocol_settings(cfg)))
    owner: dict[str, Path] = {}
    for src, m in sources.items():
        if m.get("settings") != want_settings:
            problems.add(f"{src}: protocol settings differ from the combined config's "
                         "(benchmark, tasks, relations, n, budgets, retry or evaluation policy)")
        for mid, ran in m.get("models", {}).items():
            if mid in owner:
                problems.add(f"model {mid!r} appears in two sources: {owner[mid]} and {src}")
            owner[mid] = src
            model = cfg.llm.model(mid)
            if model is None:
                problems.add(f"{src}: model {mid!r} is not in the combined config")
            elif ran != model.effective_condition():
                problems.add(f"{src}: model {mid!r} ran {ran!r}, the combined config says "
                             f"{model.effective_condition()!r}")
    if set(owner) != set(cfg.model_ids()):
        problems.add(f"source models {sorted(owner)} != combined config models {sorted(cfg.model_ids())}")


# ---------------------------------------------------------------------------
# Coverage and prompt identity
# ---------------------------------------------------------------------------

def _generate_dir(root: Path, stage: str, label: str) -> Path:
    return root / stage / "generate" / label


def merge_rq2(cfg: Config, labels: list[str], sources: dict[Path, dict], owner: dict[str, Path],
              problems: _Problems, allow_failures: bool) -> dict[str, dict]:
    """``{label: {"completions": ..., "meta": ..., "failures": [...]}}``."""
    n = cfg.rq2.n_completions
    relations = cfg.rq2.relations
    out: dict[str, dict] = {}
    for label in labels:
        completions = {r: {} for r in relations}
        meta = {r: {} for r in relations}
        failures: list[dict] = []
        base_prompt: dict[str, tuple[str, str]] = {}
        for mid in cfg.model_ids():
            src = owner[mid]
            d = _generate_dir(src, "rq2", label)
            comp_path, meta_path = d / "completions.json", d / "generation_meta.json"
            if not comp_path.is_file() or not meta_path.is_file():
                problems.add(f"rq2 {label}: {src} has no completions.json/generation_meta.json")
                continue
            comp, gmeta = _read_json(comp_path), _read_json(meta_path)
            done = (d / "_done.marker").exists()
            for r in relations:
                cell = (comp.get(r) or {}).get(mid)
                cmeta = (gmeta.get(r) or {}).get(mid)
                if cell is None or cmeta is None:
                    problems.add(f"rq2 {label} / {r} / {mid}: cell missing in {src}")
                    continue
                if len(cell) == n and cmeta.get("status") == "ok":
                    pass
                elif len(cell) == 0 and cmeta.get("status") in FAILURE_STATUSES:
                    if allow_failures:
                        failures.append({"relation": r, "model_id": mid,
                                         "status": cmeta.get("status"),
                                         "error": cmeta.get("error"), "source": str(src)})
                    else:
                        problems.add(f"rq2 {label} / {r} / {mid}: {cmeta.get('status')} "
                                     f"({cmeta.get('error')}); rerun, or --allow-failures")
                else:
                    problems.add(f"rq2 {label} / {r} / {mid}: {len(cell)} completions, "
                                 f"status {cmeta.get('status')!r} (expected {n} and 'ok')")
                bp = cmeta.get("base_prompt_sha256")
                if bp is None:
                    problems.add(f"rq2 {label} / {r} / {mid}: no base_prompt_sha256 recorded")
                elif r in base_prompt and base_prompt[r][0] != bp:
                    problems.add(f"rq2 {label} / {r}: logical prompt differs between "
                                 f"{base_prompt[r][1]} and {mid}")
                else:
                    base_prompt.setdefault(r, (bp, mid))
                completions[r][mid] = cell
                meta[r][mid] = cmeta
            if not done and not any(f["model_id"] == mid for f in failures):
                problems.add(f"rq2 {label}: {src} never marked it done")
            extra = set(comp) - set(relations)
            if extra:
                problems.add(f"rq2 {label}: {src} has relations outside the config: {sorted(extra)}")
        out[label] = {"completions": completions, "meta": meta, "failures": failures}
    return out


def merge_rq1(cfg: Config, labels: list[str], owner: dict[str, Path], problems: _Problems,
              allow_failures: bool) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for label in labels:
        mutants: list[dict] = []
        meta: dict[str, dict] = {}
        failures: list[dict] = []
        prompt_by_attempt: dict[int, tuple[str, str]] = {}
        per_source_cache: dict[Path, tuple[list, dict, dict | None, bool]] = {}
        for mid in cfg.model_ids():
            src = owner[mid]
            if src not in per_source_cache:
                d = _generate_dir(src, "rq1", label)
                if not (d / "llm_mutants.json").is_file() or not (d / "generation_meta.json").is_file():
                    problems.add(f"rq1 {label}: {src} has no llm_mutants.json/generation_meta.json")
                    per_source_cache[src] = ([], {}, None, False)
                else:
                    failed = (_read_json(d / "generation_failed.json")
                              if (d / "generation_failed.json").is_file() else None)
                    per_source_cache[src] = (_read_json(d / "llm_mutants.json"),
                                             _read_json(d / "generation_meta.json"), failed,
                                             (d / "_done.marker").exists())
            src_mutants, src_meta, src_failed, done = per_source_cache[src]
            if not done:
                problems.add(f"rq1 {label}: {src} never marked it done")
            mine = [m for m in src_mutants if m.get("source_model") == mid]
            mmeta = src_meta.get(mid)
            if mmeta is None:
                problems.add(f"rq1 {label} / {mid}: no generation_meta entry in {src}")
                continue
            failed_ids = {f["model_id"] for f in (src_failed or {}).get("failed_models", [])}
            if mid in failed_ids or not mine:
                if allow_failures and mid in failed_ids:
                    failures.append({"model_id": mid, "source": str(src),
                                     "error": next(f.get("last_error") for f in src_failed["failed_models"]
                                                   if f["model_id"] == mid)})
                else:
                    problems.add(f"rq1 {label} / {mid}: no mutants (generation failed in {src}); "
                                 "rerun, or --allow-failures")
            for att in mmeta.get("attempts", []):
                k, sha = att.get("attempt"), att.get("prompt_sha256")
                if sha is None:
                    problems.add(f"rq1 {label} / {mid}: attempt {k} has no prompt_sha256")
                elif k in prompt_by_attempt and prompt_by_attempt[k][0] != sha:
                    problems.add(f"rq1 {label} attempt {k}: prompt differs between "
                                 f"{prompt_by_attempt[k][1]} and {mid}")
                else:
                    prompt_by_attempt.setdefault(k, (sha, mid))
            mutants.extend(mine)
            meta[mid] = mmeta
        stray = {m.get("source_model") for src in set(owner.values())
                 for m in per_source_cache.get(src, ([], {}, None, False))[0]} - set(cfg.model_ids())
        if stray:
            problems.add(f"rq1 {label}: mutants from models outside the config: {sorted(stray)}")
        ids = [m["mutant_id"] for m in mutants]
        if len(ids) != len(set(ids)):
            problems.add(f"rq1 {label}: duplicate mutant ids after merge")
        out[label] = {"mutants": mutants, "meta": meta, "failures": failures}
    return out


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def _target_conflicts(path: Path, data) -> bool:
    """True if ``path`` exists with different content (compared as parsed JSON)."""
    if not path.exists():
        return False
    try:
        return _read_json(path) != json.loads(json.dumps(data))
    except json.JSONDecodeError:
        return True


def plan_writes(cfg: Config, rq2: dict | None, rq1: dict | None) -> list[tuple[Path, str, object]]:
    writes: list[tuple[Path, str, object]] = []
    for label, d in (rq2 or {}).items():
        out = task_dir(cfg, "rq2", label, phase="generate")
        writes.append((out, "completions.json", d["completions"]))
        writes.append((out, "generation_meta.json", d["meta"]))
        if d["failures"]:
            writes.append((out, "generation_failed.json",
                           {"task_label": label, "empty_cells": d["failures"],
                            "note": "transport failures carried through by --allow-failures"}))
    for label, d in (rq1 or {}).items():
        out = task_dir(cfg, "rq1", label, phase="generate")
        writes.append((out, "llm_mutants.json", d["mutants"]))
        writes.append((out, "generation_meta.json", d["meta"]))
        if d["failures"]:
            writes.append((out, "generation_failed.json",
                           {"task_label": label, "failed_models": d["failures"],
                            "note": "carried through by --allow-failures"}))
    return writes


def run_manifest(src: Path, manifest: dict, phases: list[str]) -> dict:
    files = {}
    for phase in phases:
        root = src / phase / "generate"
        if root.is_dir():
            for p in sorted(root.rglob("*")):
                if p.is_file():
                    files[p.relative_to(src).as_posix()] = _sha256_file(p)
    serving = {p.name: _read_json(p) for p in sorted(src.glob("serving_*.json"))}
    body = {"models": sorted(manifest.get("models", {})),
            "models_ran": manifest.get("models", {}),
            "serving": serving,
            "manifest_sha256": _sha256_file(src / MANIFEST_NAME),
            "files": files}
    return {"source": str(src), **body}


def merge(source_dirs: list[Path], cfg: Config, phases: list[str], allow_failures: bool = False,
          dry_run: bool = False, tasks=None) -> dict:
    problems = _Problems()
    sources = {src: load_manifest(src) for src in source_dirs}
    check_identities(cfg, sources, problems)
    problems.raise_if_any("identity checks failed")

    owner = {mid: src for src, m in sources.items() for mid in m["models"]}
    if tasks is None:
        from meta_real_eval.benchmarks import get_benchmark
        tasks = get_benchmark(cfg).load_tasks(cfg.benchmark.tasks)
    labels = [t.label for t in tasks]

    rq2 = merge_rq2(cfg, labels, sources, owner, problems, allow_failures) if "rq2" in phases else None
    rq1 = merge_rq1(cfg, labels, owner, problems, allow_failures) if "rq1" in phases else None
    problems.raise_if_any("coverage / prompt-identity checks failed")

    writes = plan_writes(cfg, rq2, rq1)
    for out, name, data in writes:
        if _target_conflicts(out / name, data):
            problems.add(f"target {out / name} exists with different content")
    problems.raise_if_any("the target is not empty and differs from this merge")

    first = next(iter(sources.values()))
    failures = {"rq2": {k: v["failures"] for k, v in (rq2 or {}).items() if v["failures"]},
                "rq1": {k: v["failures"] for k, v in (rq1 or {}).items() if v["failures"]}}
    provenance = {
        "merged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "merge_git_commit": _git_commit(),
        "phases": phases,
        "n_tasks": len(labels),
        "allow_failures": allow_failures,
        "failures": failures,
        "sources": [run_manifest(src, m, phases) for src, m in sources.items()],
    }
    if dry_run:
        return provenance

    for out, name, data in writes:
        write_json(out, name, data)
    for label in labels:
        for phase in phases:
            mark_done(task_dir(cfg, phase, label, phase="generate"))

    target = Path(cfg.project.output_dir)
    union = {
        "format": 2,
        "settings": first["settings"],
        "models": {mid: rec for m in sources.values() for mid, rec in m["models"].items()},
        "sessions": [s for m in sources.values() for s in m.get("sessions", [])]
                    + [{"phase": "merge", "at": provenance["merged_at"],
                        "git_commit": provenance["merge_git_commit"],
                        "sources": [str(s) for s in source_dirs]}],
    }
    write_json(target, MANIFEST_NAME, union)
    write_json(target, "merge_provenance.json", provenance)
    return provenance


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("sources", nargs="+", type=Path)
    ap.add_argument("--config", required=True, help="the combined config (all models)")
    ap.add_argument("--phases", default="rq1,rq2",
                    help="comma list of rq1,rq2 (reduced conditions: rq2)")
    ap.add_argument("--allow-failures", action="store_true",
                    help="carry documented transport failures through as explicit missing cells")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    phases = [p.strip() for p in args.phases.split(",") if p.strip()]
    bad = set(phases) - set(PHASES)
    if bad:
        raise MergeError(f"ERROR: unknown phase(s) {sorted(bad)}")
    cfg = Config.from_yaml(args.config)
    target = Path(cfg.project.output_dir).resolve()
    for s in args.sources:
        if s.resolve() == target or target in s.resolve().parents or s.resolve() in target.parents:
            raise MergeError(f"ERROR: source {s} overlaps the target {target}")
    prov = merge(args.sources, cfg, phases, allow_failures=args.allow_failures,
                 dry_run=args.dry_run)
    print(json.dumps({k: prov[k] for k in ("n_tasks", "failures")}, indent=2))
    print(("DRY RUN: nothing written" if args.dry_run else f"merged into {target}"))


if __name__ == "__main__":
    main()
