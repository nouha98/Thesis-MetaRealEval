"""Mutant-fault coupling (Stage 2b, protocol_freeze_decisions.md section 9 / D8). Pure functions.

Inputs per task are plain data: the valid tests (id -> stratum "p" | "gen"), mutant groups
``{"id", "source": operator|llm_whole|mixed, "models": [...], "detect": set}`` and solution groups
``{"id", "models": [...], "detect": set, "invalid": bool, "p_pass": bool|None}``. Nothing here
executes code or knows the benchmark.

Measures (Chen et al., ASE'20; equalisation, behavioural deduplication and the lift are ours):

* pc(m, f) = |K(m) & D(f)| / |K(m)|; strict <=> pc == 1; FC = share of D covered by the goals.
* Equalised source value: the EXACT expectation over every size-k subset of the source's goals
  (k = min of the two sources' goal counts), via order statistics -- the limit of random draws.
* lift = equalised PC - its mean under B permutations of D's labels within the p / gen strata
  (|D| per stratum and every |K| preserved).

Sets are Python ints (bit i = test i): intersection is ``&``, size is ``int.bit_count``.
"""

from __future__ import annotations

import hashlib
import random
from math import comb
from typing import Iterable, Optional

SOURCES = ("operator", "llm_whole")

# Frozen parameters (written to config/extensions_protocol/coupling_v1.json by freeze_coupling.py).
SPEC = {
    "version": 1,
    "primary_pool": {"n_generated": 120, "seed_offset": 1, "max_calls": 6, "timeout_s": 5.0,
                     "detect_levels": [["api_visible", "valid"], ["nontermination", "valid"]],
                     "runs": 2},
    "perturbed_pool": {"n_items": 200, "rule": "observe/raises step tokens whose types are all builtins, "
                                                 "or exception types; never end:<var>, exec steps, opaque or own-class"},
    "pool_size_check_n_generated": 40,
    "null_permutations": 200,
    "equalisation": "exact expectation over all size-k subsets, k = min(#operator goals, #eligible LLM goals)",
    "fault_categories": ["near_miss", "total_failure", "invalid_artifact", "undetected_on_pool"],
    "mixed_groups": "excluded from comparisons",
    "cross_model_rule": "an LLM goal is eligible for a fault class only if no model of the goal produced a member",
    "power_rule_min_tasks": 30,
    "primary": "per-task mean lift(llm_whole) - lift(operator) over contributing fault classes; paired Wilcoxon "
               "(statistics.wilcoxon_test) + task-cluster bootstrap CI; two-sided, alpha 0.05",
    "secondary_holm": ["strict_share", "fault_coverage", "hidden_fault_strict_share_p_live"],
    # detections are reference-relative (D7); p_fail_faults_only keeps faults confirmed by a P assertion
    "sensitivity": ["perturbed_pool", "pool_size_40", "total_failures_included", "p_fail_faults_only",
                    "unstratified_null", "no_deduplication", "unequalised_max"],
}


def bits(ids: Iterable[str], index: dict[str, int]) -> int:
    out = 0
    for t in ids:
        if t in index:
            out |= 1 << index[t]
    return out


def pc(k: int, d: int) -> Optional[float]:
    n = k.bit_count()
    return (k & d).bit_count() / n if n else None


def fault_category(d: int, n_tests: int, invalid: bool) -> str:
    if invalid:
        return "invalid_artifact"
    c = d.bit_count()
    if c == 0:
        return "undetected_on_pool"
    return "total_failure" if c == n_tests else "near_miss"


def dedup(items: list[dict]) -> list[dict]:
    """Behavioural deduplication: items with the same detection set collapse into one, with the
    union of their ids and models."""
    out: dict[int, dict] = {}
    for it in items:
        g = out.setdefault(it["bits"], {"bits": it["bits"], "ids": [], "models": set()})
        g["ids"].append(it["id"])
        g["models"] |= set(it.get("models") or [])
    return sorted(out.values(), key=lambda g: min(g["ids"]))


def eligible(items: list[dict], fault_models: set) -> list[dict]:
    """Cross-model rule. Applied to mutant groups BEFORE deduplication (section 9.2): applied to
    goals instead, one own-model group would make an identical-K cross-model group ineligible."""
    return [g for g in items if not (set(g.get("models") or []) & fault_models)]


# ---------------------------------------------------------------------------
# Exact expectations over random size-k subsets
# ---------------------------------------------------------------------------

def expected_max(values: list[float], k: int) -> float:
    """E[max of a uniformly random size-k subset] = sum_i v_(i) C(i-1, k-1) / C(n, k)."""
    v = sorted(values)
    n = len(v)
    total = comb(n, k)
    return sum(v[i] * comb(i, k - 1) for i in range(k - 1, n)) / total


def expected_any(flags: list[bool], k: int) -> float:
    n, n1 = len(flags), sum(flags)
    return 1.0 - comb(n - n1, k) / comb(n, k)


def expected_coverage(goal_bits: list[int], d: int, k: int) -> float:
    """E[|D & union of a random size-k subset of goals| / |D|]: per test t in D,
    P(covered) = 1 - C(n - c_t, k) / C(n, k), c_t = number of goals containing t."""
    n, total = len(goal_bits), comb(len(goal_bits), k)
    nd = d.bit_count()
    acc, rest, i = 0.0, d, 0
    while rest:
        if rest & 1:
            c_t = sum((g >> i) & 1 for g in goal_bits)
            acc += 1.0 - comb(n - c_t, k) / total
        rest >>= 1
        i += 1
    return acc / nd


def source_values(goal_bits: list[int], d: int, k: int) -> dict:
    pcs = [pc(g, d) for g in goal_bits]
    return {"pc": expected_max(pcs, k), "strict": expected_any([x == 1.0 for x in pcs], k),
            "fc": expected_coverage(goal_bits, d, k), "mean_pc": sum(pcs) / len(pcs),
            "max_pc_unequalised": max(pcs)}


# ---------------------------------------------------------------------------
# Null
# ---------------------------------------------------------------------------

def seed_of(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:16], 16)


def permuted(d: int, strata: list[list[int]], rng: random.Random) -> int:
    """D with its members moved to random positions within each stratum (counts preserved)."""
    out = 0
    for pos in strata:
        c = sum((d >> i) & 1 for i in pos)
        for i in rng.sample(pos, c):
            out |= 1 << i
    return out


def null_pc(goal_bits: list[int], d: int, k: int, strata: list[list[int]], B: int, seed: int) -> float:
    rng = random.Random(seed)
    return sum(expected_max([pc(g, dd) for g in goal_bits], k)
               for dd in (permuted(d, strata, rng) for _ in range(B))) / B


# ---------------------------------------------------------------------------
# One task
# ---------------------------------------------------------------------------

def task_analysis(task: str, tests: dict[str, str], mutants: list[dict], solutions: list[dict],
                  B: int = 200, seed: int = 0, include_total_failures: bool = False,
                  stratified_null: bool = True, deduplicate: bool = True, equalise: bool = True,
                  fault_filter=None, mutant_filter=None, counts_only: bool = False) -> dict:
    """Coupling for one task. ``tests``: valid test id -> stratum. Returns the exclusion reason (or
    None), descriptive counts and, when the task contributes, per-source means over contributing
    fault classes plus the per-class values. ``fault_filter`` / ``mutant_filter`` restrict the
    populations (hidden faults / P-live mutants for secondary (c))."""
    ids = sorted(tests)
    index = {t: i for i, t in enumerate(ids)}
    n_tests = len(ids)
    strata = ([[index[t] for t in ids if tests[t] == s] for s in sorted(set(tests.values()))]
              if stratified_null else [list(range(n_tests))])
    out = {"task": task, "n_tests": n_tests, "n_tests_by_stratum": {s: sum(v == s for v in tests.values())
                                                                     for s in sorted(set(tests.values()))}}
    muts = [{**m, "bits": bits(m["detect"], index)} for m in mutants if mutant_filter is None or mutant_filter(m)]
    sols = [{**s, "bits": bits(s["detect"], index)} for s in solutions]
    out["mutants"] = {src: {"groups": sum(m["source"] == src for m in muts),
                            "detected": sum(m["source"] == src and m["bits"] != 0 for m in muts)}
                      for src in ("operator", "llm_whole", "mixed")}
    cats = {}
    for s in sols:
        s["category"] = fault_category(s["bits"], n_tests, s.get("invalid", False))
        cats[s["category"]] = cats.get(s["category"], 0) + 1
    out["solution_categories"] = cats
    if n_tests == 0:
        return {**out, "excluded": "no_valid_pool"}
    keep = {"near_miss", "total_failure"} if include_total_failures else {"near_miss"}
    faults = [s for s in sols if s["category"] in keep and (fault_filter is None or fault_filter(s))]
    if deduplicate:
        classes = dedup(faults)
    else:
        classes = [{"bits": s["bits"], "ids": [s["id"]], "models": set(s.get("models") or [])} for s in faults]
    def to_goals(groups: list[dict]) -> list[dict]:
        return dedup(groups) if deduplicate else [
            {"bits": m["bits"], "ids": [m["id"]], "models": set(m.get("models") or [])} for m in groups]

    detected = {src: [m for m in muts if m["source"] == src and m["bits"] != 0] for src in SOURCES}
    goals = {src: to_goals(detected[src]) for src in SOURCES}
    out["goals"] = {src: len(g) for src, g in goals.items()}
    out["n_fault_classes"] = len(classes)
    if not classes:
        return {**out, "excluded": "no_near_miss_fault"}
    if not goals["operator"]:
        return {**out, "excluded": "no_detected_operator"}
    if not goals["llm_whole"]:
        return {**out, "excluded": "no_detected_llm"}
    if counts_only:              # technical pilot: population only, no coupling value is computed
        n = sum(bool(eligible(detected["llm_whole"], c["models"])) for c in classes)
        return {**out, "excluded": None if n else "no_cross_model_llm", "n_contributing": n}
    per_class = []
    for c in classes:
        op = goals["operator"]
        cross = eligible(detected["llm_whole"], c["models"])      # filter first, then deduplicate
        if not cross:
            continue
        llm = to_goals(cross)
        own = [m for m in detected["llm_whole"] if m not in cross]
        k = min(len(op), len(llm)) if equalise else None
        row = {"ids": c["ids"], "models": sorted(c["models"]), "size": c["bits"].bit_count(), "k": k}
        for src, gs in (("operator", op), ("llm_whole", llm)):
            gb = [g["bits"] for g in gs]
            kk = k if equalise else len(gb)
            v = source_values(gb, c["bits"], kk)
            v["null_pc"] = null_pc(gb, c["bits"], kk, strata, B, seed_of(seed, task, min(c["ids"]), src))
            v["lift"] = v["pc"] - v["null_pc"]
            v["n_goals"] = len(gb)
            row[src] = v
        row["llm_same_model_max_pc"] = max(pc(m["bits"], c["bits"]) for m in own) if own else None  # descriptive
        per_class.append(row)
    if not per_class:
        return {**out, "excluded": "no_cross_model_llm"}
    means = {}
    for src in SOURCES:
        means[src] = {key: sum(r[src][key] for r in per_class) / len(per_class)
                      for key in ("pc", "lift", "strict", "fc", "mean_pc", "max_pc_unequalised", "null_pc")}
    return {**out, "excluded": None, "n_contributing": len(per_class), "means": means,
            "delta_lift": means["llm_whole"]["lift"] - means["operator"]["lift"], "classes": per_class}


def exclusion_counts(results: list[dict]) -> dict:
    out: dict[str, int] = {}
    for r in results:
        key = r["excluded"] or "contributing"
        out[key] = out.get(key, 0) + 1
    return out
