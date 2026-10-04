"""The architectural principle of the Tier 2 port, enforced.

    Benchmark-specific code may know whether a task is a function or a
    class. RQ, statistics and analysis code must not.

Two layers (plan review rev. 2, #8), over every module under ``stage0/``,
``rq1``..``rq4/`` and ``analysis/``:

HARD (fails the build)
    * importing a concrete benchmark module: ``core.data_loader`` (HumanEval's
      loader), ``benchmarks.humaneval``, ``benchmarks.realclasseval``;
    * a comparison against ``<...>.benchmark.name`` (branching on which
      benchmark is running instead of on a declared capability).

SOFT (reported, never fails)
    * a benchmark name as a string literal in executable code. Docstrings and
      comments are ignored; this exists to make drift visible.

The RQ modules predate the adapter and still import HumanEval's loader
directly; migrating them is the remaining adapter work. They are listed in
``LEGACY_ALLOWLIST`` so the test can be strict *today*: any NEW violation
fails, and so does an allowlisted violation that has been fixed but not
removed from the list (a ratchet -- the list can only shrink, and it is
always exactly the outstanding migration work).
"""

from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "meta_real_eval"
GUARDED_DIRS = ("stage0", "rq1", "rq2", "rq3", "rq4", "analysis")
CONCRETE_MODULES = ("core.data_loader", "benchmarks.humaneval", "benchmarks.realclasseval")
BENCHMARK_NAMES = ("humaneval", "realclasseval")

# module (relative to the package) -> the concrete modules it still imports.
# Shrink this as each module is migrated to benchmarks.get_benchmark().
LEGACY_ALLOWLIST: dict[str, set[str]] = {
    # rq1/kill_rate.py, rq1/llm_mutator.py: the legacy HumanEvalTask-typed
    # functions (compute_kill_matrix, generate_llm_mutants, ...) stay for
    # anything that still calls them directly; rq1/runner.py itself (the only
    # production caller) is migrated and calls the generic ones instead.
    "rq1/kill_rate.py": {"core.data_loader"},
    "rq1/llm_mutator.py": {"core.data_loader"},
    "rq2/corpus.py": {"core.data_loader"},
    # rq3/divergence.py: the legacy HumanEvalTask-typed compute_divergence /
    # _pick_best_completion stay for direct callers; rq3/runner.py (the only
    # production caller) is migrated and calls the generic ones instead.
    "rq3/divergence.py": {"core.data_loader"},
    # rq4/consistency.py, rq4/interaction.py: the legacy HumanEvalTask-typed
    # build_consistency_assertions / compute_tau_at_degradation_level stay
    # for direct callers; rq4/runner.py (the only production caller) is
    # migrated and calls the generic ones (via Benchmark.consistency_suite /
    # compute_tau_at_degradation_level_generic) instead.
    "rq4/consistency.py": {"core.data_loader"},
    "rq4/interaction.py": {"core.data_loader"},
    # stage0/equivalence.py: check_equivalence / compute_canonical_outputs
    # (both HumanEvalTask-typed) stay for rq1/runner.py, not yet migrated.
    # The generic check_equivalence_generic / compute_canonical_observations
    # in the same file are benchmark-agnostic and carry no such dependency.
    "stage0/equivalence.py": {"core.data_loader"},
}


def _guarded_modules() -> list[Path]:
    return sorted(p for d in GUARDED_DIRS for p in (PKG / d).glob("*.py"))


def _resolve(rel: str, node: ast.ImportFrom) -> list[str]:
    """Dotted names (relative to the package) this import pulls in.

    ``rel`` is the importing module's path relative to the package root.
    """
    parts = list(Path(rel).with_suffix("").parts[:-1])
    if node.level:
        base = parts[: len(parts) - (node.level - 1)] if node.level > 1 else parts
    else:
        mod = node.module or ""
        base = mod.split(".")[1:] if mod.startswith("meta_real_eval") else None
        if base is None:
            return []
        return [".".join(base)] + [".".join(base + [a.name]) for a in node.names]
    target = base + (node.module.split(".") if node.module else [])
    return [".".join(target)] + [".".join(target + [a.name]) for a in node.names]


def hard_violations(source: str, rel: str) -> set[str]:
    tree = ast.parse(source)
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            found |= {m for m in _resolve(rel, node) if m in CONCRETE_MODULES}
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("meta_real_eval."):
                    name = alias.name.split(".", 1)[1]
                    if name in CONCRETE_MODULES:
                        found.add(name)
        elif isinstance(node, ast.Compare):
            for side in [node.left, *node.comparators]:
                if ast.unparse(side).endswith("benchmark.name"):
                    found.add("compare:benchmark.name")
    return found


def soft_violations(module: Path) -> list[str]:
    tree = ast.parse(module.read_text(encoding="utf-8"))
    docstrings = {
        id(n.body[0].value) for n in ast.walk(tree)
        if isinstance(n, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and n.body and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)
    }
    return [
        f"line {n.lineno}: {n.value!r}" for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings
        and n.value.lower() in BENCHMARK_NAMES
    ]


def test_no_new_benchmark_specific_dependencies():
    new, fixed = [], []
    for module in _guarded_modules():
        rel = module.relative_to(PKG).as_posix()
        found = hard_violations(module.read_text(encoding="utf-8"), rel)
        allowed = LEGACY_ALLOWLIST.get(rel, set())
        new += [f"{rel}: {v}" for v in sorted(found - allowed)]
        fixed += [f"{rel}: {v}" for v in sorted(allowed - found)]
    assert not new, "benchmark-specific dependency in RQ code (use benchmarks.get_benchmark):\n  " + "\n  ".join(new)
    assert not fixed, "migrated -- remove from LEGACY_ALLOWLIST:\n  " + "\n  ".join(fixed)


def test_allowlist_only_names_existing_modules():
    for rel in LEGACY_ALLOWLIST:
        assert (PKG / rel).exists(), rel


def test_soft_benchmark_name_literals_report(capsys):
    """Never fails: prints benchmark-name literals in executable RQ code."""
    hits = {m.relative_to(PKG).as_posix(): soft_violations(m) for m in _guarded_modules()}
    hits = {k: v for k, v in hits.items() if v}
    with capsys.disabled():
        if hits:
            print("\n[architecture soft check] benchmark-name literals in RQ code:")
            for k, v in hits.items():
                print(f"  {k}: {', '.join(v)}")


def test_checker_catches_planted_violations():
    """The checker itself must work, for every import spelling."""
    rel = "rq2/probe.py"
    cases = {
        "from ..core.data_loader import X\n": {"core.data_loader"},
        "from ..core import data_loader\n": {"core.data_loader"},
        "from meta_real_eval.benchmarks.realclasseval import X\n": {"benchmarks.realclasseval"},
        "import meta_real_eval.benchmarks.humaneval\n": {"benchmarks.humaneval"},
        "if cfg.benchmark.name == 'humaneval':\n    pass\n": {"compare:benchmark.name"},
        "from ..benchmarks import get_benchmark\n": set(),          # the sanctioned route
        "from ..benchmarks.base import Task\n": set(),
    }
    for src, expected in cases.items():
        assert hard_violations(src, rel) == expected, src
