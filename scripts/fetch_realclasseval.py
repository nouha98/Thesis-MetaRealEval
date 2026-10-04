#!/usr/bin/env python
"""Pre-stage the RealClassEval corpus (Tier 2) for offline SLURM jobs.

Like ``scripts/fetch_data.py``, run this **once on the login node** (which has
internet). It sparse-clones the authors' replication package at a pinned commit,
joins the three artefacts each task needs, and writes one gzipped JSONL row per
task:

    csn|post_cut-off/dfs/<variant>_docstr.csv          skeleton + metrics
    .../human_written_classes/full_docstr/human/snippet_N.py   reference
    .../pynguin_generated_tests/full_docstr/test_snippet_N.py  Pynguin suite

    .venv/bin/python scripts/fetch_realclasseval.py

Outputs (``data/realclasseval/``):

``realclasseval_v1.jsonl.gz``  one row per task that has a CSV row, a reference
                               and a test file.
``dataset_summary.json``       what was actually found, per split. The task
                               ceiling is *discovered* here, never assumed:
                               the paper headlines 200 classes per split, but
                               the package ships a different number of suites.
``source.json``                pinned commit and the corpus sha256.

Nothing is filtered on runnability here; that is the validity gate's job
(``scripts/validate_realclasseval.py``). This script only refuses rows it cannot
join.

Re-running is a no-op unless ``--force`` is given.
"""

from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import json
import re
import subprocess
import sys
import warnings
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

REPO_URL = "https://github.com/mrsumitbd/RealClassEval-Replication.git"
# Pinned 2026-09-27. Changing it changes the corpus, so bump CORPUS_VERSION too.
PINNED_SHA = "c731c55de8fba337a8bc49eb6637a7fd9b5e32c6"
CORPUS_VERSION = "v1"

SPLITS = ("csn", "post_cut-off")
VARIANTS = ("full_docstr", "partial_docstr", "no_docstr")
DATA_SUBDIR = "data/functional_correctness_data"

DEFAULT_SRC = REPO_ROOT / "cache" / "realclasseval_src"
DEFAULT_DEST = REPO_ROOT / "data" / "realclasseval"

# Columns that are identifiers or code; every other CSV column is a numeric
# Understand metric and goes into ``metrics``.
_NON_METRIC_COLUMNS = {
    "id", "repository_name", "file_path", "class_name",
    "human_written_code", "class_skeleton", "snippet_id",
}

csv.field_size_limit(2**31 - 1)


# ---------------------------------------------------------------------------
# Source checkout
# ---------------------------------------------------------------------------

def _git(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{proc.stderr.strip()}")
    return proc.stdout.strip()


def checkout(src: Path, sha: str) -> None:
    """Sparse, blobless checkout of just the two splits at ``sha``."""
    if not (src / ".git").is_dir():
        src.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", "--filter=blob:none", "--no-checkout", "--quiet",
              REPO_URL, str(src)], cwd=src.parent)
        _git(["sparse-checkout", "init", "--cone"], cwd=src)
        _git(["sparse-checkout", "set", *(f"{DATA_SUBDIR}/{s}" for s in SPLITS)], cwd=src)
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=src,
                          capture_output=True, text=True)
    if head.returncode != 0 or head.stdout.strip() != sha:
        _git(["fetch", "--quiet", "origin", sha], cwd=src)
    # Always check out, even when HEAD already equals ``sha``: after a
    # --no-checkout clone HEAD resolves but the working tree is still empty.
    _git(["checkout", "--quiet", sha], cwd=src)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _read_text(path: Path) -> str:
    # The package ships CRLF files. Normalising line endings is semantically
    # lossless for Python source and keeps skeleton/reference/test consistent.
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def _snippet_num(name: str) -> int:
    return int(re.search(r"(\d+)", name).group(1))


def _read_csv(path: Path) -> dict[int, dict]:
    with path.open(encoding="utf-8", newline="") as f:
        return {_snippet_num(r["snippet_id"]): r for r in csv.DictReader(f)}


def _parses(src: str) -> bool:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            ast.parse(src)
            return True
        except SyntaxError:
            return False


def _top_level_imports(src: str) -> list[str]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return []
    return [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]


def _defines_class(src: str, short_name: str) -> bool:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            tree = ast.parse(src)
        except SyntaxError:
            return bool(re.search(rf"^class\s+{re.escape(short_name)}\b", src, re.M))
    return any(isinstance(n, ast.ClassDef) and n.name == short_name for n in tree.body)


def _test_composition(test_src: str) -> dict:
    """Count what the Pynguin suite is made of. Purely descriptive."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            tree = ast.parse(test_src)
        except SyntaxError:
            return {"parses": False}
    tests = [n for n in tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")]

    def is_xfail(fn) -> bool:
        return any("xfail" in ast.unparse(d) for d in fn.decorator_list)

    def uses_raises(fn) -> bool:
        return any(isinstance(n, ast.With) and "pytest.raises" in ast.unparse(n) for n in ast.walk(fn))

    return {
        "parses": True,
        "n_tests": len(tests),
        "n_xfail": sum(is_xfail(t) for t in tests),
        "n_pytest_raises": sum(uses_raises(t) for t in tests),
        "n_with_assert": sum(any(isinstance(n, ast.Assert) for n in ast.walk(t)) for t in tests),
    }


def _metric(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def build_split(root: Path, split: str) -> tuple[list[dict], dict]:
    base = root / DATA_SUBDIR / split
    csvs = {v: _read_csv(base / "dfs" / f"{v}.csv") for v in VARIANTS}
    ref_dir = base / "human_written_classes" / "full_docstr" / "human"
    test_dir = base / "pynguin_generated_tests" / "full_docstr"
    refs = {_snippet_num(p.name): p for p in ref_dir.glob("snippet_*.py")}
    tests = {_snippet_num(p.name): p for p in test_dir.glob("test_snippet_*.py")}
    full = csvs["full_docstr"]

    summary: dict = {
        "csv_rows": {v: len(csvs[v]) for v in VARIANTS},
        "unique_snippets": len(full),
        "reference_files": len(refs),
        "test_files": len(tests),
        "missing_reference": sorted(set(full) - set(refs)),
        "missing_tests": len(set(full) - set(tests)),
        "tests_without_csv_row": sorted(set(tests) - set(full)),
        "tests_without_reference": sorted(set(tests) - set(refs)),
        "class_name_mismatch": [],
        "reference_unparseable": [],
        "skeleton_unparseable": [],
    }

    rows: list[dict] = []
    for num in sorted(set(full) & set(refs) & set(tests)):
        r = full[num]
        short = r["class_name"].split(".")[-1]
        reference = _read_text(refs[num])
        test_code = _read_text(tests[num])
        skeleton = r["class_skeleton"].replace("\r\n", "\n")

        if not _defines_class(reference, short):
            summary["class_name_mismatch"].append(num)
            continue
        if not _parses(reference):
            summary["reference_unparseable"].append(num)
        if not _parses(skeleton):
            summary["skeleton_unparseable"].append(num)

        def variant_skeleton(v: str):
            row = csvs[v].get(num)
            return row["class_skeleton"].replace("\r\n", "\n") if row else None

        rows.append({
            "task_id": f"RealClassEval/{split}/snippet_{num}",
            "split": split,
            "snippet_id": f"snippet_{num}",
            "snippet_num": num,
            "csv_id": r["id"],
            "repository_name": r["repository_name"],
            "source_file_path": r["file_path"],
            "class_name": r["class_name"],
            "class_short_name": short,
            "skeleton_full_docstr": skeleton,
            "skeleton_partial_docstr": variant_skeleton("partial_docstr"),
            "skeleton_no_docstr": variant_skeleton("no_docstr"),
            "reference_code": reference,
            "test_code": test_code,
            "skeleton_imports": _top_level_imports(skeleton),
            "reference_imports": _top_level_imports(reference),
            "test_composition": _test_composition(test_code),
            "metrics": {k: _metric(v) for k, v in r.items() if k not in _NON_METRIC_COLUMNS},
        })

    summary["matched"] = len(rows)
    summary["skeleton_has_imports"] = sum(bool(x["skeleton_imports"]) for x in rows)
    summary["reference_has_imports"] = sum(bool(x["reference_imports"]) for x in rows)
    summary["has_partial_docstr"] = sum(x["skeleton_partial_docstr"] is not None for x in rows)
    summary["has_no_docstr"] = sum(x["skeleton_no_docstr"] is not None for x in rows)
    comp = [x["test_composition"] for x in rows if x["test_composition"].get("parses")]
    summary["tests"] = {
        "suites_unparseable": sum(not x["test_composition"].get("parses") for x in rows),
        "suites_with_zero_tests": sum(c["n_tests"] == 0 for c in comp),
        **{k: sum(c[k] for c in comp)
           for k in ("n_tests", "n_xfail", "n_pytest_raises", "n_with_assert")},
    }
    return rows, summary


def write_jsonl_gz(rows: list[dict], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    # mtime=0 so the gzip bytes, and therefore the sha256, are reproducible.
    with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
        for row in rows:
            gz.write((json.dumps(row, sort_keys=True) + "\n").encode("utf-8"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sha", default=PINNED_SHA, help="replication-package commit")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC,
                        help=f"sparse checkout location (default: {DEFAULT_SRC})")
    parser.add_argument("--dest", type=Path, default=DEFAULT_DEST,
                        help=f"output directory (default: {DEFAULT_DEST})")
    parser.add_argument("--force", action="store_true",
                        help="rebuild even if the corpus is already present")
    args = parser.parse_args()

    corpus_path = args.dest / f"realclasseval_{CORPUS_VERSION}.jsonl.gz"
    if corpus_path.exists() and not args.force:
        print(f"{corpus_path} already exists — nothing to do (use --force to refresh).")
        return 0

    try:
        checkout(args.src, args.sha)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    all_rows: list[dict] = []
    summary: dict = {}
    for split in SPLITS:
        rows, summary[split] = build_split(args.src, split)
        all_rows.extend(rows)

    sha256 = write_jsonl_gz(all_rows, corpus_path)
    (args.dest / "dataset_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (args.dest / "source.json").write_text(json.dumps({
        "repo": REPO_URL,
        "commit": args.sha,
        "corpus_version": CORPUS_VERSION,
        "corpus_file": corpus_path.name,
        "corpus_sha256": sha256,
        "n_tasks": len(all_rows),
        "line_endings": "CRLF normalised to LF",
    }, indent=2) + "\n", encoding="utf-8")

    for split in SPLITS:
        s = summary[split]
        print(f"{split:>13}: {s['matched']} tasks joined "
              f"({s['unique_snippets']} CSV rows, {s['reference_files']} references, "
              f"{s['test_files']} suites; {s['tests']['n_tests']} tests, "
              f"{s['tests']['n_xfail']} xfail, {s['tests']['n_pytest_raises']} pytest.raises)")
    print(f"Wrote {len(all_rows)} tasks to {corpus_path}\n  sha256 {sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
