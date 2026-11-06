"""RQ4 for Tier 2 (RealClassEval): oracle-unit degradation (plan rev. 6, section 8).

Primary design ``units``: remove ``ceil(level * n)`` oracle units per task --
assert units are weakened to their bare expression, exception tests leave the
suite (``benchmarks/oracle_units.py``). Secondary design ``tests``: the whole-test
degradation (``RealClassEvalBenchmark.degrade``), only on tasks with enough valid
tests to keep one at every level (68 tasks). Tier 1's RQ4 (``rq4/runner.py``) is
untouched: the runner dispatches here on ``bench.rq4_design == "oracle_units"``.

Fixed before any RQ4 result, per score (graded ``mean_primary`` primary, binary
``pass@1`` secondary), a task is analysed iff
  1. >= 1 unit (design ``tests``: valid test) is left at every level,
  2. the intact-suite ranking is defined (the models are not all tied on the
     ``original`` prompt, RQ2 v3 scores), and
  3. the level-0.0 baseline check passes: every completion's ``primary`` and
     ``passed_all`` under the intact suite equal RQ2 v3's exactly, through the
     same path (build_solution with no-class scoring, a warm-up reference run, a
     pool of cpu_workers, an isolated re-run of whole-suite timeouts). A
     completion that still differs after one isolated re-run fails the task.
A level with no unit left is missing: never executed, never a zero.

H1a's primary score is pass@1, a deviation decided after the full run
(2026-11-06): under the graded score the up-to-20 consistency assertions enter
the denominator of 3-9-test suites and dominate it (shown exactly from the stored
scores), so graded rank recovery mostly measures the assertions' own share.
pass@1 has no denominator to dilute. The graded H1a is reported beside it, as
pre-registered and, post hoc, with the assertions counted as one test. H1b keeps
the graded score as primary. Rankings compare scores as exact fractions
(rq2.ranking.comparable), and the analysis recomputes every level summary from
the stored cells, so files written before that rule are read under it.
"""

from __future__ import annotations

import logging
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from typing import Optional

import numpy as np

from ..benchmarks import get_benchmark
from ..benchmarks.base import DegradedSuite, SuiteResult
from ..benchmarks.oracle_units import ASSERT_UNIT, min_units_for_levels
from ..core.checkpoint import clear_done, is_done, mark_done, read_json, task_dir, write_json
from ..core.config import BASELINE_RELATION, Config
from ..rq2.evaluator import _warm_up, _whole_suite_timed_out, pass_at_k
from ..rq2.ranking import _rank_vector, _tau_b, cell_is_scored, collapse_tau_by_arm, comparable

logger = logging.getLogger(__name__)

SCORES = ("mean_primary", "pass@1")
UNITS, TESTS = "units", "tests"
DESIGN_VERSION = "oracle_units_v1"
DEGRADE_FILE = "degradation_tier2.json"
AUGMENT_FILE = "augment_tier2.json"


class CellCrash(RuntimeError):
    """An evaluation worker crashed: a harness fault, so the task stays open."""


# ---------------------------------------------------------------------------
# Eligibility (pre-treatment)
# ---------------------------------------------------------------------------

def eligibility(task, bench, cfg: Config, pass_rates: dict) -> dict:
    """The fixed rules 1-2 for both designs and both scores (rule 3 is checked
    at run time). Reads only the gate, the test file and RQ2 v3's scores."""
    units = bench.oracle_units(task)
    n_valid = len(bench._gated(task))
    need = min_units_for_levels(cfg.rq4.degradation_levels)
    models = cfg.model_ids()
    base = pass_rates.get(BASELINE_RELATION, {})
    out = {
        "n_units": len(units),
        "n_assert_units": sum(u.kind == ASSERT_UNIT for u in units),
        "n_exception_units": sum(u.kind != ASSERT_UNIT for u in units),
        "n_valid_tests": n_valid,
        "min_required": need,
        "designs": {UNITS: {}, TESTS: {}},
    }
    for key in SCORES:
        vals = [comparable(base[m][key]) for m in models if cell_is_scored(base.get(m, {}), key)]
        ranking_defined = len(vals) == len(models) and len(set(vals)) > 1
        for design, n, what in ((UNITS, len(units), "oracle units"), (TESTS, n_valid, "valid tests")):
            reasons = []
            if n < need:
                reasons.append(f"fewer than {need} {what} ({n})")
            if not ranking_defined:
                reasons.append("intact ranking undefined (models tied on the original prompt)")
            out["designs"][design][key] = {"eligible": not reasons, "reasons": reasons}
    return out


def _runs(elig: dict, design: str) -> bool:
    return any(v["eligible"] for v in elig["designs"][design].values())


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _score_under_suite(task, completion: str, cfg: Config, timeout_s: float, suite) -> SuiteResult:
    """Picklable worker; ``suite=None`` is exactly RQ2's _score_completion call."""
    bench = get_benchmark(cfg)
    return bench.run_suite(task, bench.build_solution(task, completion), timeout_s, suite=suite)


def score_cells(task, cfg: Config, completions_data: dict, suite) -> dict:
    """{(relation, model): ([SuiteResult], [re-run indices])}, scored as RQ2 v3
    scores: one pool of cpu_workers, then whole-suite timeouts re-run alone."""
    timeout_s = cfg.execution.timeout_s
    results: dict[tuple[str, str], list] = {}
    with ProcessPoolExecutor(max_workers=cfg.execution.cpu_workers) as pool:
        futures = {(rel, m): [pool.submit(_score_under_suite, task, c, cfg, timeout_s, suite) for c in comps]
                   for rel, by_model in completions_data.items() for m, comps in by_model.items()}
        for cell, fs in futures.items():
            out = []
            for f in fs:
                try:
                    out.append(f.result())
                except Exception as exc:
                    raise CellCrash(f"{task.label} {cell}: evaluation worker crashed: {exc}") from exc
            results[cell] = out
    reruns: dict[tuple[str, str], list[int]] = {}
    for (rel, m), rs in results.items():
        for i, r in enumerate(rs):
            if _whole_suite_timed_out(r):
                reruns.setdefault((rel, m), []).append(i)
                rs[i] = _score_under_suite(task, completions_data[rel][m][i], cfg, timeout_s, suite)
    return {cell: (rs, reruns.get(cell, [])) for cell, rs in results.items()}


def _cell_record(rs: list[SuiteResult], reruns: list[int]) -> dict:
    primary = [r.primary for r in rs]
    passed = [bool(r.passed_all) for r in rs]
    n = len(rs)
    return {
        "n": n,
        "primary_scores": primary,
        "per_completion": passed,
        "mean_primary": (sum(primary) / n) if n and all(p is not None for p in primary) else None,
        "pass@1": pass_at_k(n, sum(passed), 1) if n else None,
        "outcome_counts": [dict(Counter(o.outcome for o in r.outcomes.values())) for r in rs],
        "n_timed_out": sum(any(o.outcome == "timeout" for o in r.outcomes.values()) for r in rs),
        "timeout_reruns": reruns,
    }


def cells_record(scored: dict) -> dict:
    out: dict[str, dict] = {}
    for (rel, m), (rs, reruns) in scored.items():
        out.setdefault(rel, {})[m] = _cell_record(rs, reruns)
    return out


def level_summary(cells: dict, model_ids: list[str], relations: list[str], key: str) -> dict:
    """RQ2's per-task ranking statistics for one score under one suite."""
    scores = {rel: {m: comparable(c[key]) for m, c in by_model.items() if c["n"] and c[key] is not None}
              for rel, by_model in cells.items()}
    complete = {rel for rel, s in scores.items() if all(m in s for m in model_ids)}
    base_ok = BASELINE_RELATION in complete
    base_vec = _rank_vector(scores.get(BASELINE_RELATION, {}), model_ids)
    tau: dict[str, Optional[float]] = {}
    for rel in relations:
        if rel == BASELINE_RELATION:
            continue
        tau[rel] = (_tau_b(base_vec, _rank_vector(scores[rel], model_ids))
                    if base_ok and rel in complete else None)
    by_arm = collapse_tau_by_arm(tau)
    defined = [t for t in tau.values() if t is not None]
    return {
        "score": key,
        "mean_tau_b": by_arm["primary"],
        "tau_b_by_arm": by_arm,
        "mean_tau_b_all_relations": float(np.mean(defined)) if defined else None,
        "tau_b_per_relation": tau,
        "degenerate_relations": [r for r in tau if r in complete and base_ok and tau[r] is None],
        "incomplete_relations": [r for r in tau if not (base_ok and r in complete)],
        "scores": scores,
    }


def _level(cells: dict, cfg: Config, **counts) -> dict:
    return {**counts, "missing": False,
            "by_score": {k: level_summary(cells, cfg.model_ids(), cfg.rq2.relations, k) for k in SCORES},
            "cells": cells}


def _missing(**counts) -> dict:
    return {**counts, "missing": True, "reason": "no oracle unit left at this level"}


# ---------------------------------------------------------------------------
# Level-0.0 baseline check
# ---------------------------------------------------------------------------

def _mismatches(scored: dict, pass_rates: dict) -> list[dict]:
    out = []
    cells = {rel: set(by_model) for rel, by_model in pass_rates.items()}
    for (rel, m), (rs, _) in scored.items():
        rq2 = pass_rates.get(rel, {}).get(m)
        if rq2 is None or not cell_is_scored(rq2, "mean_primary") or rq2.get("primary_scores") is None:
            out.append({"relation": rel, "model": m, "index": None, "reason": "no scored RQ2 cell"})
            continue
        cells[rel].discard(m)
        if len(rq2["primary_scores"]) != len(rs):
            out.append({"relation": rel, "model": m, "index": None, "reason": "completion count differs"})
            continue
        for i, r in enumerate(rs):
            if r.primary != rq2["primary_scores"][i] or bool(r.passed_all) != rq2["per_completion"][i]:
                out.append({"relation": rel, "model": m, "index": i, "reason": "score differs",
                            "rq4": [r.primary, bool(r.passed_all)],
                            "rq2": [rq2["primary_scores"][i], rq2["per_completion"][i]]})
    out += [{"relation": rel, "model": m, "index": None, "reason": "RQ2 cell not re-scored"}
            for rel, ms in cells.items() for m in sorted(ms)]
    return out


def baseline_check(task, cfg: Config, completions_data: dict, scored: dict, pass_rates: dict) -> dict:
    """Compare level 0.0 with RQ2 v3, re-running each mismatching completion once,
    alone. Updates ``scored`` in place with the re-run results."""
    first = _mismatches(scored, pass_rates)
    rerun = [x for x in first if x["index"] is not None]
    for x in rerun:
        rs, _ = scored[(x["relation"], x["model"])]
        rs[x["index"]] = _score_under_suite(task, completions_data[x["relation"]][x["model"]][x["index"]],
                                            cfg, cfg.execution.timeout_s, None)
    final = _mismatches(scored, pass_rates) if first else []
    n = sum(len(rs) for rs, _ in scored.values())
    return {"ok": not final, "n_completions": n, "n_mismatch_first_pass": len(first),
            "rerun_alone": [(x["relation"], x["model"], x["index"]) for x in rerun],
            "mismatches": final}


def _monotonicity(levels: dict, worse_when_removed: bool = True) -> dict:
    """``passed_all`` may only go up as units are removed (a removed check cannot
    newly fail a completion); counted, never corrected."""
    keys = sorted((k for k, v in levels.items() if not v["missing"]), key=float)
    violations = []
    for a, b in zip(keys, keys[1:]):
        for rel, by_model in levels[a]["cells"].items():
            for m, ca in by_model.items():
                cb = levels[b]["cells"].get(rel, {}).get(m)
                if cb is None:
                    continue
                for i, (pa, pb) in enumerate(zip(ca["per_completion"], cb["per_completion"])):
                    if pa and not pb:
                        violations.append({"from": a, "to": b, "relation": rel, "model": m, "index": i})
    return {"n_violations": len(violations), "examples": violations[:20]}


# ---------------------------------------------------------------------------
# Degrade phase
# ---------------------------------------------------------------------------

def run_degrade_tier2(task, cfg: Config, bench, force: bool = False) -> None:
    label = task.label
    out = task_dir(cfg, "rq4", label, phase="degrade")
    if force:
        clear_done(out)
    if is_done(out):
        logger.info("SKIP degrade %s", label)
        return
    try:
        completions = read_json(task_dir(cfg, "rq2", label, phase="generate"), "completions.json")
        pass_rates = read_json(task_dir(cfg, "rq2", label, phase="evaluate"), "pass_rates.json")
    except FileNotFoundError:
        logger.error("%s: RQ2 completions or pass_rates missing -- run RQ2 first", label)
        return

    seed = cfg.project.seed
    levels = list(cfg.rq4.degradation_levels)
    elig = eligibility(task, bench, cfg, pass_rates)
    _, info0 = bench.degrade_units(task, 0.0, seed)
    _, info_top = bench.degrade_units(task, 1.0, seed)
    record = {
        "design_version": DESIGN_VERSION, "task": label, "task_id": task.task_id,
        "seed": seed, "levels": levels, "eligibility": elig,
        "units": {"ids": [u.unit_id for u in bench.oracle_units(task)],
                  "removal_order": info_top["removed"]},
        "executed": False,
    }
    run_units, run_tests = _runs(elig, UNITS), _runs(elig, TESTS)
    if not (run_units or run_tests):
        write_json(out, DEGRADE_FILE, record)
        mark_done(out)
        logger.info("%s: not eligible under any design/score -- not executed", label)
        return

    try:
        _warm_up(bench, task, cfg.execution.timeout_s, label)
        scored0 = score_cells(task, cfg, completions, None)
        record["baseline_check"] = check = baseline_check(task, cfg, completions, scored0, pass_rates)
        if not check["ok"]:
            write_json(out, DEGRADE_FILE, record)
            mark_done(out)
            logger.error("%s: level 0.0 does not reproduce RQ2 v3 (%d completion(s)) -- degraded "
                         "levels not run, task excluded from the analysis", label, len(check["mismatches"]))
            return
        cells0 = cells_record(scored0)
        designs: dict[str, dict] = {}
        if run_units:
            lv = {"0.0": _level(cells0, cfg, degradation_level=0.0, n_units=info0["n_units"],
                                n_removed=0, n_remaining=info0["n_units"], removed=[])}
            for level in (l for l in levels if l > 0):
                suite, info = bench.degrade_units(task, level, seed)
                counts = dict(degradation_level=level, **info)
                lv[str(level)] = (_missing(**counts) if info["n_remaining"] == 0 else
                                  _level(cells_record(score_cells(task, cfg, completions, suite)), cfg, **counts))
            designs[UNITS] = {"levels": lv, "monotonicity": _monotonicity(lv)}
        if run_tests:
            n_valid = elig["n_valid_tests"]
            lv = {"0.0": _level(cells0, cfg, degradation_level=0.0, n_tests=n_valid, n_removed=0,
                                n_remaining=n_valid, shared_with=UNITS if run_units else None)}
            for level in (l for l in levels if l > 0):
                suite = bench.degrade(task, level, seed=seed)
                kept = len(suite.subset) if suite.subset is not None else n_valid
                counts = dict(degradation_level=level, n_tests=n_valid, n_removed=n_valid - kept,
                              n_remaining=kept)
                lv[str(level)] = (_missing(**counts) if kept == 0 else
                                  _level(cells_record(score_cells(task, cfg, completions, suite)), cfg, **counts))
            designs[TESTS] = {"levels": lv, "monotonicity": _monotonicity(lv)}
    except CellCrash as exc:
        logger.error("%s -- not marked done; re-run degrade", exc)
        return

    record["designs"] = designs
    record["executed"] = True
    write_json(out, DEGRADE_FILE, record)
    mark_done(out)
    logger.info("%s: degraded (%s); baseline check ok over %d completions", label,
                ", ".join(designs), record["baseline_check"]["n_completions"])


# ---------------------------------------------------------------------------
# Augment phase
# ---------------------------------------------------------------------------

def _degraded_suite(bench, task, design: str, level: float, seed: int):
    if level == 0:
        return DegradedSuite(level=0.0)
    if design == UNITS:
        return bench.degrade_units(task, level, seed)[0]
    return bench.degrade(task, level, seed=seed)


def run_augment_tier2(task, cfg: Config, bench, force: bool = False) -> None:
    label = task.label
    threshold = cfg.rq3.divergence_threshold
    if threshold is None:
        raise SystemExit("Tier 2 RQ4 augment needs the calibrated rq3.divergence_threshold "
                         "(scripts/calibrate_tau_div_tier2.py); it never augments with an "
                         "uncalibrated default.")
    out = task_dir(cfg, "rq4", label, phase="augment")
    if force:
        clear_done(out)
    if is_done(out):
        logger.info("SKIP augment %s", label)
        return
    try:
        deg = read_json(task_dir(cfg, "rq4", label, phase="degrade"), DEGRADE_FILE)
    except FileNotFoundError:
        logger.error("%s: %s missing -- run rq4 degrade first", label, DEGRADE_FILE)
        return
    record = {"design_version": DESIGN_VERSION, "task": label, "divergence_threshold": threshold}
    if not deg.get("executed") or not deg.get("baseline_check", {}).get("ok"):
        record["skipped"] = "not executed in degrade (ineligible or failed baseline check)"
        write_json(out, AUGMENT_FILE, record)
        mark_done(out)
        return
    try:
        divergence = read_json(task_dir(cfg, "rq3", label, phase="execute"), "divergence.json")
        completions = read_json(task_dir(cfg, "rq2", label, phase="generate"), "completions.json")
    except FileNotFoundError:
        logger.error("%s: RQ3 divergence.json or RQ2 completions missing", label)
        return

    ca_code, n_ca = bench.consistency_suite(task, divergence, threshold)
    record.update(has_consistency_assertions=bool(ca_code), n_consistency_assertions=n_ca,
                  divergence_rate=divergence.get("pairwise_disagreement_rate"), designs={})
    seed = cfg.project.seed
    shared0 = None
    try:
        if ca_code:
            _warm_up(bench, task, cfg.execution.timeout_s, label)
        for design, dd in deg["designs"].items():
            lv: dict[str, dict] = {}
            for key, dlev in dd["levels"].items():
                counts = {k: v for k, v in dlev.items() if k not in ("by_score", "cells", "missing", "reason")}
                if dlev["missing"]:
                    lv[key] = _missing(**counts)
                elif not ca_code:
                    # Nothing to add: the augmented suite IS the degraded one.
                    lv[key] = {**dlev, "reused_degraded": True}
                elif float(key) == 0 and shared0 is not None:
                    lv[key] = {**shared0, **counts}
                else:
                    degraded = _degraded_suite(bench, task, design, float(key), seed)
                    suite = bench.augmented_suite(task, degraded, ca_code, n_ca)
                    lv[key] = _level(cells_record(score_cells(task, cfg, completions, suite)), cfg, **counts)
                    if float(key) == 0:
                        shared0 = lv[key]
            record["designs"][design] = {"levels": lv,
                                         "monotonicity_vs_degraded": _aug_vs_degraded(dd["levels"], lv)}
    except CellCrash as exc:
        logger.error("%s -- not marked done; re-run augment", exc)
        return
    write_json(out, AUGMENT_FILE, record)
    mark_done(out)
    logger.info("%s: augmented with %d consistency assertion(s)", label, n_ca)


def _aug_vs_degraded(deg_levels: dict, aug_levels: dict) -> dict:
    """Augmentation only adds checks, so ``passed_all`` may never rise."""
    violations = []
    for key, a in aug_levels.items():
        d = deg_levels.get(key)
        if a["missing"] or d is None or d["missing"]:
            continue
        for rel, by_model in a["cells"].items():
            for m, ca in by_model.items():
                cd = d["cells"].get(rel, {}).get(m)
                for i, (pd, pa) in enumerate(zip(cd["per_completion"] if cd else [], ca["per_completion"])):
                    if pa and not pd:
                        violations.append({"level": key, "relation": rel, "model": m, "index": i})
    return {"n_violations": len(violations), "examples": violations[:20]}


# ---------------------------------------------------------------------------
# Analyze phase
# ---------------------------------------------------------------------------

def _mean_n(values: list) -> dict:
    v = [x for x in values if x is not None]
    return {"mean": float(np.mean(v)) if v else None, "n": len(v)}


def _rescore(designs: dict, cfg: Config) -> None:
    """Recompute every executed level's summaries from its stored cells, in place."""
    for dd in designs.values():
        for lv in dd["levels"].values():
            if not lv["missing"]:
                lv["by_score"] = {k: level_summary(lv["cells"], cfg.model_ids(), cfg.rq2.relations, k)
                                  for k in SCORES}


def _block_weighted(deg: dict, aug: dict, design: str, k: str) -> Optional[dict]:
    """{model: graded score} on the original prompt under the augmented suite with the
    consistency assertions counted as ONE test, scored by the fraction of them passed
    (post hoc). Recovered from the stored scores: an augmented completion's graded score
    is (tests passed + assertions passed) / (n + c), so the assertions it passed are
    augmented * (n + c) - degraded * n. None if that is not a whole number in [0, c]."""
    d, a = deg["designs"][design]["levels"][k], aug["designs"][design]["levels"][k]
    c = aug["n_consistency_assertions"]
    n = (d["n_remaining"] if design == TESTS else          # units: removed exception tests leave
         deg["eligibility"]["n_valid_tests"] - sum("#" not in u for u in d["removed"]))
    scores = {}
    for m, ca in a["cells"][BASELINE_RELATION].items():
        per = []
        for pa, pd in zip(ca["primary_scores"], d["cells"][BASELINE_RELATION][m]["primary_scores"]):
            passed = pa * (n + c) - pd * n
            if abs(passed - round(passed)) > 1e-6 or not 0 <= round(passed) <= c:
                return None
            per.append((pd * n + round(passed) / c) / (n + 1))
        scores[m] = comparable(sum(per) / len(per))
    return scores


def analyze_tier2(cfg: Config, tasks) -> dict:
    """Per design x score: eligibility, H1b (Page's L), ranking collapse, H1a."""
    from ..analysis.statistics import cochran_q, pages_l_test, wilcoxon_test
    from .runner import _mde, _rank_recovery

    models = cfg.model_ids()
    records, augments = {}, {}
    for task in tasks:
        try:
            records[task.label] = read_json(task_dir(cfg, "rq4", task.label, phase="degrade"), DEGRADE_FILE)
        except FileNotFoundError:
            continue
        try:
            augments[task.label] = read_json(task_dir(cfg, "rq4", task.label, phase="augment"), AUGMENT_FILE)
        except FileNotFoundError:
            pass
    for r in (*records.values(), *augments.values()):
        _rescore(r.get("designs", {}), cfg)

    checked = {t: r["baseline_check"] for t, r in records.items() if "baseline_check" in r}
    failed = sorted(t for t, c in checked.items() if not c["ok"])
    summary = {
        "design_version": DESIGN_VERSION,
        "n_tasks_with_file": len(records),
        "n_tasks_executed": sum(bool(r.get("executed")) for r in records.values()),
        "baseline_check": {"n_checked": len(checked), "n_failed": len(failed), "failed_tasks": failed,
                           "n_completions": sum(c["n_completions"] for c in checked.values()),
                           "n_rerun_alone": sum(len(c["rerun_alone"]) for c in checked.values())},
        "primary": {"h1b": f"{UNITS}/mean_primary", "h1a": f"{UNITS}/pass@1",
                    "note": "H1a on pass@1 is a post-run deviation: the graded score is diluted "
                            "by the assertions, see rq4/tier2.py"},
        "designs": {},
    }
    levels = [str(l) for l in cfg.rq4.degradation_levels]
    for design in (UNITS, TESTS):
        summary["designs"][design] = {}
        for key in SCORES:
            reasons, eligible = Counter(), []
            for t, r in records.items():
                e = r["eligibility"]["designs"][design][key]
                if not e["eligible"]:
                    reasons.update(x.split(" (")[0] for x in e["reasons"])   # drop the per-task count
                elif t in failed:
                    reasons["baseline check failed"] += 1
                elif r.get("executed") and design in r.get("designs", {}):
                    eligible.append(t)
            res = {"n_eligible": len(eligible), "ineligible_reasons": dict(reasons),
                   "eligible_tasks": sorted(eligible)}
            lvl = {t: records[t]["designs"][design]["levels"] for t in eligible}
            # every model tied on the original prompt (eligible tasks have no missing level)
            collapsed = {t: [len(set(lvl[t][k]["by_score"][key]["scores"][BASELINE_RELATION].values())) <= 1
                             for k in levels] for t in eligible}
            taus = {t: [lvl[t][k]["by_score"][key]["mean_tau_b"] for k in levels] for t in eligible
                    if all(not lvl[t][k]["missing"] for k in levels)}
            res["h1b_pages_l"] = pages_l_test(list(taus.values()), descending=True)
            # Page's L needs tau_b at every level, so it sees only the tasks degradation did
            # not break: a collapsed ranking has no tau_b. Counted, so the survivorship shows.
            dropped = [t for t, v in taus.items() if None in v]
            intact_undefined = {t for t in dropped if taus[t][0] is None}     # not degradation's doing
            res["h1b_excluded"] = {
                "no tau_b on the intact suite": len(intact_undefined),
                "ranking collapsed at a degraded level": sum(any(collapsed[t]) for t in dropped
                                                             if t not in intact_undefined),
                "a paraphrase ranking tied otherwise": sum(not any(collapsed[t]) for t in dropped
                                                           if t not in intact_undefined)}
            res["tau_b_by_level"] = {
                k: {"llm": _mean_n([lvl[t][k]["by_score"][key]["mean_tau_b"] for t in eligible]),
                    "control": _mean_n([lvl[t][k]["by_score"][key]["tau_b_by_arm"]["control"] for t in eligible])}
                for k in levels}
            res["ranking_collapse"] = {k: sum(c[i] for c in collapsed.values())
                                       for i, k in enumerate(levels) if i}
            res["ranking_collapse_cochran_q"] = (
                {**cochran_q([[int(x) for x in c] for c in collapsed.values()]),
                 "note": "post hoc; 0/1 per task and level (the intact level included): "
                         "every model tied on the original prompt"} if collapsed else None)
            res["monotonicity_violations"] = sum(records[t]["designs"][design]["monotonicity"]["n_violations"]
                                                 for t in eligible)
            # H1a's estimand: tasks where augmentation can change anything, i.e. that got
            # >= 1 consistency assertion (a task without one reuses its degraded results,
            # so its recovery is exactly 0 by construction). Fixed before any augmented
            # result existed; the pooled population is reported beside it.
            res["h1a"] = _h1a(eligible, lvl, augments, design, key, levels, models,
                              _rank_recovery, _mde, wilcoxon_test, only_ca=True)
            res["h1a_all_eligible"] = _h1a(eligible, lvl, augments, design, key, levels, models,
                                           _rank_recovery, _mde, wilcoxon_test, only_ca=False)
            if key == "mean_primary":
                res["h1a_block_weighted"] = _h1a(
                    eligible, lvl, augments, design, key, levels, models, _rank_recovery, _mde,
                    wilcoxon_test, only_ca=True,
                    aug_scores=lambda t, k: _block_weighted(records[t], augments[t], design, k))
            summary["designs"][design][key] = res
    return summary


def _h1a(eligible, lvl, augments, design, key, levels, models, rank_recovery, mde, wilcoxon,
         only_ca: bool = False, aug_scores=None) -> dict:
    """Rank recovery against the intact ranking. ``aug_scores(task, level)`` gives the
    augmented original-prompt scores (default: the level summary's); None drops the pair."""
    if aug_scores is None:
        aug_scores = (lambda t, k: augments[t]["designs"][design]["levels"][k]
                      ["by_score"][key]["scores"][BASELINE_RELATION])
    with_aug = [t for t in eligible if t in augments and design in augments[t].get("designs", {})]
    n_aug = len(with_aug)
    if only_ca:
        with_aug = [t for t in with_aug if augments[t].get("has_consistency_assertions")]
    if not with_aug:
        return {"available": False, "n_augmented_tasks": n_aug,
                "note": ("no eligible task received a consistency assertion" if n_aug else
                         "no augment results (run rq4 augment after RQ3 calibration)")}
    out = {"available": True, "population": "tasks with >= 1 consistency assertion" if only_ca
           else "all eligible tasks (those without assertions contribute recovery 0)",
           "n_tasks": len(with_aug),
           "n_with_consistency_assertions": sum(bool(augments[t].get("has_consistency_assertions"))
                                                for t in with_aug),
           "monotonicity_violations": sum(augments[t]["designs"][design]["monotonicity_vs_degraded"]["n_violations"]
                                          for t in with_aug),
           "by_level": {}}
    for k in levels:
        deg_r, aug_r = [], []
        for t in with_aug:
            intact = lvl[t]["0.0"]["by_score"][key]["scores"][BASELINE_RELATION]
            a = augments[t]["designs"][design]["levels"][k]
            if lvl[t][k]["missing"] or a["missing"]:
                continue
            sa = aug_scores(t, k)
            rd = rank_recovery(intact, lvl[t][k]["by_score"][key]["scores"][BASELINE_RELATION], models)
            ra = None if sa is None else rank_recovery(intact, sa, models)
            if rd is not None and ra is not None:
                deg_r.append(rd)
                aug_r.append(ra)
        entry = {"n_pairs": len(deg_r)}
        if deg_r:
            entry.update(mean_rho_degraded=float(np.mean(deg_r)), mean_rho_augmented=float(np.mean(aug_r)),
                         mean_recovery=float(np.mean(aug_r) - np.mean(deg_r)))
            if k != "0.0":
                entry["wilcoxon_augmented_vs_degraded"] = wilcoxon(aug_r, deg_r)
                entry["minimum_detectable_effect"] = mde(aug_r, deg_r)
            else:
                entry["note"] = ("intact suite plus consistency assertions: rho < 1 means the "
                                 "assertions alone moved the intact ranking (consensus bias)")
                entry["n_moved"] = sum(r < 1 for r in aug_r)
        out["by_level"][k] = entry
    return out


def report(summary: dict) -> str:
    lines = ["RQ4 (Tier 2) -- oracle-unit degradation (primary) and whole-test sensitivity",
             f"tasks with a degrade file: {summary['n_tasks_with_file']}, executed: {summary['n_tasks_executed']}"]
    bc = summary["baseline_check"]
    lines.append(f"level-0.0 baseline check: {bc['n_checked']} task(s), {bc['n_completions']} completions, "
                 f"failed {bc['n_failed']} {bc['failed_tasks'][:10]}, re-run alone {bc['n_rerun_alone']}")
    pr = summary["primary"]
    lines.append(f"primary: H1b {pr['h1b']}, H1a {pr['h1a']} ({pr['note']})")
    for design, by_score in summary["designs"].items():
        for key, r in by_score.items():
            tag = {pr["h1b"]: "PRIMARY for H1b", pr["h1a"]: "PRIMARY for H1a"}.get(f"{design}/{key}", "secondary")
            lines.append(f"\n== design={design} score={key} [{tag}]  eligible={r['n_eligible']}  "
                         f"ineligible={r['ineligible_reasons']}")
            lines.append(f"   monotonicity violations: {r['monotonicity_violations']}")
            for k, v in r["tau_b_by_level"].items():
                llm, ctl = v["llm"], v["control"]
                fmt = lambda x: "  n/a" if x["mean"] is None else f"{x['mean']:.3f}"
                lines.append(f"   level {k}: tau_b llm={fmt(llm)} (n={llm['n']})  control={fmt(ctl)} "
                             f"(n={ctl['n']})  collapsed={r['ranking_collapse'].get(k, '-')}")
            q = r["ranking_collapse_cochran_q"]
            if q and q["q"] is not None:
                lines.append(f"   ranking collapse across levels, Cochran's Q (post hoc): Q={q['q']:.2f} "
                             f"p={q['p_value']:.3g} n={q['n_blocks']}")
            p = r["h1b_pages_l"]
            lines.append("   H1b Page's L: " + (f"L={p['L']} z={p['z']} p={p['p_value']} n={p['n_blocks']}"
                                               if p.get("L") is not None else f"n/a ({p.get('note')})")
                         + f"  excluded: {r['h1b_excluded']}")
            _report_h1a(lines, "H1a (tasks with assertions)", r["h1a"])
            if key == "mean_primary":
                lines.append("     (graded: the assertions enter the denominator and dominate it)")
            _report_h1a(lines, "H1a, secondary (all eligible tasks)", r["h1a_all_eligible"])
            if "h1a_block_weighted" in r:
                _report_h1a(lines, "H1a, post hoc (the assertions counted as one test)", r["h1a_block_weighted"])
    return "\n".join(lines)


def _report_h1a(lines: list, title: str, h: dict) -> None:
    if not h.get("available"):
        lines.append(f"   {title}: {h.get('note')}")
        return
    lines.append(f"   {title}: {h['n_tasks']} task(s), {h['n_with_consistency_assertions']} with assertions, "
                 f"monotonicity violations {h['monotonicity_violations']}")
    for k, e in h["by_level"].items():
        if not e["n_pairs"]:
            lines.append(f"     level {k}: no defined pair")
            continue
        w = e.get("wilcoxon_augmented_vs_degraded", {})
        lines.append(f"     level {k}: rho degraded={e['mean_rho_degraded']:+.3f} augmented="
                     f"{e['mean_rho_augmented']:+.3f} recovery={e['mean_recovery']:+.3f} "
                     f"n={e['n_pairs']}" + (f" p={w['p_value']:.4g}" if w else f" moved={e.get('n_moved')}"))


def run_analyze_tier2(cfg: Config, tasks) -> dict:
    summary = analyze_tier2(cfg, tasks)
    out = cfg.project.output_dir / "rq4" / "summary"
    out.mkdir(parents=True, exist_ok=True)
    write_json(out, "tier2_rq4.json", summary)
    text = report(summary)
    (out / "tier2_rq4.txt").write_text(text + "\n", encoding="utf-8")
    print(text)
    return summary


# ---------------------------------------------------------------------------
# Audit: do the consensus assertions agree with the ground truth?
# ---------------------------------------------------------------------------

def reference_on_assertions(task, cfg: Config, bench, ca_code: str, n_ca: int) -> dict:
    """The task's REFERENCE implementation under the intact suite plus the consensus
    assertions. An assertion the reference fails demands behaviour the benchmark's own
    solution does not have, so it counts against the consensus, not the model.
    Level-0 augmented rankings move exactly where such assertions fail someone."""
    suite = bench.augmented_suite(task, DegradedSuite(level=0.0), ca_code, n_ca)
    r = bench.run_suite(task, task.reference_code, cfg.execution.timeout_s, suite=suite)
    outcomes = {n: r.outcomes[n].outcome for n in (f"test_ca_{i}" for i in range(n_ca)) if n in r.outcomes}
    passed = sum(o == "ordinary_pass" for o in outcomes.values())
    return {"n_assertions": n_ca, "n_run": len(outcomes), "reference_passes": passed,
            "reference_fails": len(outcomes) - passed, "reference_primary": r.primary,
            "outcomes": outcomes}
