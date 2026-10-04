"""M0: validate one RealClassEval task before it may enter the experiment.

Applies D1-D6 to a raw corpus task and returns one JSON-serialisable record
for the manifest. ``scripts/validate_realclasseval.py`` runs this over the
corpus, in parallel, with per-task checkpoints, and writes the manifest and
the gate report.

Order of checks (cheapest and most decisive first):

1. Static, task-level: the skeleton must parse (``malformed_skeleton``,
   amendment A4); the suite must import the class at all
   (``invalid_vacuous_suite``, A3).
2. Reference import, via the first scenario run: an ImportError /
   ModuleNotFoundError is ``missing_dependency`` -- the runtime check the
   dependency scanner explicitly defers to.
3. D2 on every test: 3 full-suite runs, an isolated run for each stable
   candidate, then the environment-assertion rule (A4) and the skeleton run
   for ``trivial``. The skeleton baseline is the reference module's import
   statements followed by the skeleton: the dataset's skeletons carry no
   imports while their signatures use them (``x: np.ndarray``), so the bare
   skeleton cannot even be imported and every test would "fail" on it,
   flagging nothing as trivial. This baseline is never shown to a model, so
   it does not touch the D7 import policy for completions.
4. D4/D5 on every original scenario: two reference runs give the
   nondeterminism mask; a scenario the reference does not complete ("ok") in
   both runs is excluded, with its status as the reason.
5. Accept iff at least one valid test and one usable scenario remain.
"""

from __future__ import annotations

import ast
import warnings
from typing import Optional

from ..core.sandbox import execute_pytest
from .base import Task
from .forkserver import run_scenarios
from .gate import (
    INVALID_ENVIRONMENT_ASSERTION,
    VALID_EXCEPTION_ORACLE,
    apply_environment_rule,
    classify_test_validity,
    mark_trivial,
)
from .observe import is_opaque, nondeterminism_mask
from .outcomes import ERROR, classify_run, static_test_info
from .scenarios import OBSERVE, UnsupportedScenario, build_pool, extract_scenarios

METRIC_KEYS = ("SumCyclomatic", "AvgCyclomatic", "MaxNesting", "CountDeclMethod",
               "CountClassCoupled", "CountLineCode")
IMPORT_FAILURES = {"EXC:builtins.ModuleNotFoundError", "EXC:builtins.ImportError"}
# Bump whenever validate_task's logic changes: it is part of the checkpoint key,
# so cached per-task records from an older gate are never reused.
GATE_VERSION = 2


def _parses(src: str) -> bool:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            ast.parse(src)
            return True
        except SyntaxError:
            return False


def skeleton_baseline(task: Task) -> str:
    """The reference's top-level imports + the skeleton: an importable class
    whose methods do nothing (see the module docstring, step 3)."""
    tree = ast.parse(task.reference_code)
    imports = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    return "\n".join(imports) + ("\n\n" if imports else "") + task.prompt


def validate_task(
    task: Task,
    suite_timeout_s: float,
    scenario_timeout_s: float,
    seed: int,
    pool_sizes: tuple[int, ...] = (500, 200),
    scenario_mode: Optional[str] = None,
) -> dict:
    row = task.raw or {}
    rec: dict = {
        "task_id": task.task_id,
        "split": task.split,
        "label": task.label,
        "status": "excluded",
        "exclusion_reason": None,
        "detail": None,
        "metrics": {k: (row.get("metrics") or {}).get(k) for k in METRIC_KEYS},
        "tests": {},
        "scenarios": {},
    }

    def exclude(reason: str, detail=None) -> dict:
        rec["exclusion_reason"], rec["detail"] = reason, detail
        return rec

    # 1. Static, task-level.
    if not _parses(task.prompt):
        return exclude("malformed_skeleton")
    try:
        header, scenarios = extract_scenarios(task.test_code, task.module_name)
    except UnsupportedScenario as e:
        vacuous = "never imports the module under test" in str(e)
        return exclude("invalid_vacuous_suite" if vacuous else "unsupported_scenario", str(e))
    statics = static_test_info(task.test_code)
    names = list(statics)
    rec["n_original_tests"] = len(names)

    # 2. Reference import (first scenario run doubles as the import check).
    run1 = run_scenarios(task.module_name, task.reference_code, header, scenarios,
                         timeout_s=scenario_timeout_s, mode=scenario_mode)
    if run1 and run1[0]["status"] == "import_error":
        exc = run1[0]["tokens"].get("import")
        return exclude("missing_dependency" if exc in IMPORT_FAILURES else "reference_import_error", exc)
    run2 = run_scenarios(task.module_name, task.reference_code, header, scenarios,
                         timeout_s=scenario_timeout_s, mode=scenario_mode)

    # 3. D2 on every test.
    def suite(code: str, select: list[str]):
        run = execute_pytest(task.module_name, code, task.test_code, timeout_s=suite_timeout_s, select=select)
        return classify_run(run, statics, requested=select)

    full_runs = [suite(task.reference_code, names) for _ in range(3)]
    gated = []
    for name in names:
        runs = [r[name] for r in full_runs]
        try:
            gated.append(classify_test_validity(runs, isolated_run=None))
        except ValueError:  # a stable candidate: confirm order-independence
            gated.append(classify_test_validity(runs, suite(task.reference_code, [name])[name]))

    by_test = {s.origin_test: s for s in scenarios}
    env_only = {
        name for name, s in ((n, by_test.get(n)) for n in names)
        if s is not None and s.env_observations_dropped > 0
        and not any(st.kind == OBSERVE for st in s.steps)
    }
    gated = apply_environment_rule(gated, env_only)

    valid_names = [g.nodeid for g in gated if g.is_valid]
    rec["skeleton_baseline"] = None
    if valid_names:
        baseline = skeleton_baseline(task)
        skel = suite(baseline, valid_names)
        rec["skeleton_baseline"] = ("import_error" if all(o.outcome == ERROR for o in skel.values())
                                    else "ok")
        gated = mark_trivial(gated, skel)

    for g in gated:
        st = statics[g.nodeid]
        rec["tests"][g.nodeid] = {
            "validity": g.validity,
            "ref_exc_type": g.ref_exc_type,
            "trivial": g.trivial,
            "source": ("explicit_pytest_raises" if st.has_pytest_raises
                       else "reference_xfail" if st.has_xfail_marker else None),
            "xfail": st.has_xfail_marker,
            "env_assertions": getattr(by_test.get(g.nodeid), "env_observations_dropped", 0),
        }

    # 4. D4/D5 on every original scenario.
    excluded: dict[str, str] = {}
    masks: dict[str, list[str]] = {}
    n_tokens = n_masked = n_opaque = 0
    for s, a, b in zip(scenarios, run1, run2):
        if a["status"] != "ok" or b["status"] != "ok":
            excluded[s.scenario_id] = f"reference_{a['status'] if a['status'] != 'ok' else b['status']}"
            continue
        mask = sorted(nondeterminism_mask(a["tokens"], b["tokens"]))
        if mask:
            masks[s.scenario_id] = mask
        n_tokens += len(a["tokens"])
        n_masked += len(mask)
        n_opaque += sum(is_opaque(t) for t in a["tokens"].values())
    usable = [s for s in scenarios if s.scenario_id not in excluded]
    rec["scenarios"] = {
        "n_original": len(scenarios),
        "n_usable": len(usable),
        "excluded": excluded,
        "masks": masks,
        "n_tokens": n_tokens,
        "n_masked_tokens": n_masked,
        "n_opaque_tokens": n_opaque,
        "env_observations_dropped": sum(s.env_observations_dropped for s in scenarios),
        "threads_at_fork": max((t.get("threads_at_fork", 1) for t in run1), default=None),
        "pools": {str(n): build_pool(header, usable, n, seed).composition() for n in pool_sizes},
    }

    # 5. Decision.
    if not valid_names:
        return exclude("no_valid_tests")
    if not usable:
        return exclude("no_usable_scenarios")
    rec["status"] = "accepted"
    return rec


def summarise_tests(rec: dict) -> dict:
    """Per-task test counts for the gate report (D2 mandatory reporting)."""
    tests = rec.get("tests", {}).values()
    valid = [t for t in tests if t["validity"] in ("valid_behavioural", VALID_EXCEPTION_ORACLE)]
    return {
        "original": rec.get("n_original_tests", 0),
        "valid": len(valid),
        "valid_behavioural": sum(t["validity"] == "valid_behavioural" for t in valid),
        "valid_exception_explicit_raises": sum(t["validity"] == VALID_EXCEPTION_ORACLE
                                               and t["source"] == "explicit_pytest_raises" for t in valid),
        "valid_exception_reference_xfail": sum(t["validity"] == VALID_EXCEPTION_ORACLE
                                               and t["source"] == "reference_xfail" for t in valid),
        "trivial": sum(t["trivial"] for t in valid),
        "xfail": sum(t["xfail"] for t in tests),
        "environment_assertion": sum(t["validity"] == INVALID_ENVIRONMENT_ASSERTION for t in tests),
    }
