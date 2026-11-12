"""Shared paths and helpers for the saturation / difficulty analysis.

Read-only on every existing result: inputs are only ever opened for reading, and everything
this analysis writes goes under ``results_saturation/`` and ``doc/saturation/``.

Final results used (plan rev. 7):
  Tier 1  results_tier1/                       (analysis_summary.json of 2026-09-26)
  Tier 2  full_v5 (rankings, analyses) + full_v4/combined (per-completion scores, RQ4 files)
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

TIER1 = REPO / "results_tier1"
T2_SCORES = REPO / "results" / "results_tier2_runs" / "full_v4" / "combined"
T2_POST = REPO / "results" / "results_tier2_runs" / "full_v5"
OUT = REPO / "results_saturation"
VIEWS = OUT / "views"
DOC = REPO / "doc" / "saturation"

# (tier, ranking file the RQ2 analysis reads, expected summary holding the reference numbers)
RANKING_RUNS = {
    "tier1": ("rankings.json", TIER1 / "analysis_summary.json"),
    "tier2_graded": ("rankings.json", T2_POST / "analysis_summary.json"),
    "tier2_pass1": ("rankings_pass1.json", T2_POST / "analysis_summary.rankings_pass1.json"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def hash_tree(root: Path, patterns: list[str]) -> dict:
    """SHA-256 of every file matching ``patterns`` under ``root`` plus one hash of the
    sorted (relative path, file hash) list."""
    files = sorted({p for pat in patterns for p in root.glob(pat) if p.is_file()})
    per_file = {p.relative_to(root).as_posix(): sha256_file(p) for p in files}
    digest = hashlib.sha256("\n".join(f"{k}:{v}" for k, v in sorted(per_file.items())).encode()).hexdigest()
    return {"root": str(root.relative_to(REPO)), "patterns": patterns, "n_files": len(per_file),
            "tree_sha256": digest, "files": per_file}


def git_state() -> dict:
    def run(*args):
        return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True).stdout.strip()
    return {"head": run("rev-parse", "HEAD"), "tags": run("tag").splitlines(),
            "dirty_tracked_files": [l for l in run("status", "--short").splitlines() if not l.startswith("??")]}


def load_analyze_results():
    """scripts/analyze_results.py as a module (its globals RESULTS/RANKINGS/EXCLUDE are set by
    the caller, exactly as the unit tests do)."""
    spec = importlib.util.spec_from_file_location("analyze_results_saturation",
                                                  REPO / "scripts" / "analyze_results.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EXCLUDE.clear()
    return module


def build_views() -> dict[str, Path]:
    """Copy (never link, never move) the per-task files each RQ2 analysis needs into one tree per
    tier: Tier 2's scores live in v4 and its final rankings in v5, so they are merged here."""
    roots = {"tier1": VIEWS / "tier1", "tier2": VIEWS / "tier2"}
    for tier, root in roots.items():
        if root.exists():
            shutil.rmtree(root)
    for src in sorted((TIER1 / "rq2" / "evaluate").iterdir()):
        if src.is_dir():
            dst = roots["tier1"] / "rq2" / "evaluate" / src.name
            dst.mkdir(parents=True)
            for name in ("pass_rates.json", "rankings.json"):
                shutil.copy2(src / name, dst / name)
    for src in sorted((T2_SCORES / "rq2" / "evaluate").iterdir()):
        if src.is_dir():
            dst = roots["tier2"] / "rq2" / "evaluate" / src.name
            dst.mkdir(parents=True)
            shutil.copy2(src / "pass_rates.json", dst / "pass_rates.json")
            for name in ("rankings.json", "rankings_pass1.json"):
                shutil.copy2(T2_POST / "rq2" / "evaluate" / src.name / name, dst / name)
    return roots


def deep_diff(expected, actual, tol: float = 1e-9, path: str = "") -> tuple[float, list[str]]:
    """Largest numeric difference and every other mismatch, comparing only the keys ``expected``
    has (a newer analysis may add keys) and skipping the prose ``note`` fields, whose wording
    changed between code versions. NaN equals NaN."""
    worst, other = 0.0, []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return worst, [f"{path}: not a dict"]
        for k, v in expected.items():
            if k == "note":
                continue
            if k not in actual:
                other.append(f"{path}/{k}: missing")
                continue
            w, o = deep_diff(v, actual[k], tol, f"{path}/{k}")
            worst, other = max(worst, w), other + o
    elif isinstance(expected, list):
        if not isinstance(actual, list) or len(expected) != len(actual):
            return worst, [f"{path}: list length"]
        for i, (x, y) in enumerate(zip(expected, actual)):
            w, o = deep_diff(x, y, tol, f"{path}[{i}]")
            worst, other = max(worst, w), other + o
    elif isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if expected != actual:
            other.append(f"{path}: {expected!r} != {actual!r}"[:140])
    elif isinstance(expected, (int, float)):
        if not isinstance(actual, (int, float)):
            return worst, [f"{path}: {expected!r} != {actual!r}"[:140]]
        if expected != expected and actual != actual:
            return worst, other
        d = abs(expected - actual)
        worst = max(worst, d)
        if d > tol:
            other.append(f"{path}: {expected!r} vs {actual!r}")
    return worst, other


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")
