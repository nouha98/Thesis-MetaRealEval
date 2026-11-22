"""Independent recompute of the coupling endpoints on 3 tasks (C3 verification; read-only).

    python scripts/coupling_recompute.py --run results_tier2_ext/coupling/full

Deliberately imports NOTHING from the project (no coupling.py, no analyze_coupling.py). From
<run>/<task>/detection.json it re-derives the data handling of protocol section 9 -- masked and
reference-unstable tests dropped, near-miss faults, behavioural deduplication, the cross-model rule
applied before deduplication -- and recomputes per class PC, strict share and FC by brute-force
enumeration of size-k subsets (Monte Carlo above a limit), and the null by its own permutation code
following 9.3 (seed = sha256(version | task | class | source); B and the version come from the frozen
coupling_v1.json). Per-task means and the LLM - operator lift are compared with <run>/endpoints.json.

Task choice: a fixed rule on task STRUCTURE only, applied before any coupling value is computed:
  (a) brute force: the contributing task with the fewest detected goals (operator + LLM);
  (b) cross-model rule: the most fault classes written by >= 2 models;
  (c) stratified null: the most P-scenario tests (with generated tests too).
Ties go to the label order; a task is used once.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FROZEN = REPO / "config" / "extensions_protocol" / "coupling_v1.json"
OBS_LIMIT, NULL_LIMIT, MC_DRAWS = 200_000, 3_000, 400
KEYS = ("pc", "strict", "fc", "null_pc", "lift")


# --- data handling (section 9.1 / 9.2), re-derived from detection.json -----------------------

def task_data(det: dict) -> dict:
    tests = dict(det["tests"]["primary"] or {})
    ref = next((p for p in det["programs"] if p["kind"] == "reference"), None)
    drop = set()
    if ref and ref.get("primary"):                       # reference-unstable tests (9.6 adjustment)
        drop |= set(ref["primary"]["detect"]) | set(ref["primary"]["masked"])
    for p in det["programs"]:                            # masked for any program: dropped for the task
        if p.get("primary"):
            drop |= set(p["primary"]["masked"])
    tests = {t: s for t, s in tests.items() if t not in drop}
    muts, sols = [], []
    for p in det["programs"]:
        if p["kind"] == "reference" or p.get("primary_error"):
            continue
        cells = p.get("primary") or {"detect": [], "import_error": True}
        d = frozenset(t for t in cells["detect"] if t in tests)
        if p["kind"] == "mutant":
            muts.append({"id": p["id"], "source": p["source"], "models": set(p.get("models") or []), "d": d})
        else:
            sols.append({"id": p["id"], "models": set(p.get("models") or []), "d": d,
                         "invalid": bool(cells.get("import_error"))})
    n = len(tests)
    near = [s for s in sols if not s["invalid"] and 0 < len(s["d"]) < n]
    classes: dict[frozenset, dict] = {}
    for s in near:                                       # behavioural deduplication of faults
        c = classes.setdefault(s["d"], {"d": s["d"], "ids": [], "models": set()})
        c["ids"].append(s["id"])
        c["models"] |= s["models"]
    detected = {src: [m for m in muts if m["source"] == src and m["d"]] for src in ("operator", "llm_whole")}
    return {"tests": tests, "classes": sorted(classes.values(), key=lambda c: min(c["ids"])), "detected": detected}


def goals(mutants: list[dict]) -> list[frozenset]:
    return sorted({m["d"] for m in mutants}, key=lambda d: sorted(d))


# --- measures, by enumeration (section 9.3) ----------------------------------------------------

def pc(k: frozenset, d: frozenset) -> float:
    return len(k & d) / len(k)


def subset_means(gs: list[frozenset], d: frozenset, k: int, rng: random.Random, limit: int) -> tuple:
    """(E[max pc], E[any pc == 1], E[coverage]) over size-k subsets; exact below ``limit``."""
    exact = math.comb(len(gs), k) <= limit
    subsets = itertools.combinations(gs, k) if exact else (rng.sample(gs, k) for _ in range(MC_DRAWS))
    tot = [0.0, 0.0, 0.0]
    count = 0
    for sub in subsets:
        pcs = [pc(g, d) for g in sub]
        tot[0] += max(pcs)
        tot[1] += any(x == 1.0 for x in pcs)
        tot[2] += len(d & frozenset().union(*sub)) / len(d)
        count += 1
    return tuple(x / count for x in tot), exact


def null_pc(gs, d, k, tests, task, cls_id, src, version, B, mc_rng) -> tuple:
    ids = sorted(tests)
    strata = [[t for t in ids if tests[t] == s] for s in sorted(set(tests.values()))]
    seed = int(hashlib.sha256("|".join(map(str, (version, task, cls_id, src))).encode()).hexdigest()[:16], 16)
    rng, total, exact = random.Random(seed), 0.0, True
    for _ in range(B):
        dd = set()
        for pos in strata:                               # permute D within each stratum, counts kept
            dd |= set(rng.sample(pos, sum(t in d for t in pos)))
        (m, _, _), ex = subset_means(gs, frozenset(dd), k, mc_rng, NULL_LIMIT)
        total, exact = total + m, exact and ex
    return total / B, exact


def recompute(det: dict, version: int, B: int) -> dict:
    td = task_data(det)
    op = goals(td["detected"]["operator"])
    mc = random.Random(0)
    rows, exact = [], True
    for c in td["classes"]:
        cross = [m for m in td["detected"]["llm_whole"] if not (m["models"] & c["models"])]   # BEFORE dedup
        if not cross:
            continue
        llm = goals(cross)
        k = min(len(op), len(llm))
        row = {}
        for src, gs in (("operator", op), ("llm_whole", llm)):
            (p, s, f), ex1 = subset_means(gs, c["d"], k, mc, OBS_LIMIT)
            nul, ex2 = null_pc(gs, c["d"], k, td["tests"], det["task"], min(c["ids"]), src, version, B, mc)
            row[src] = {"pc": p, "strict": s, "fc": f, "null_pc": nul, "lift": p - nul}
            exact = exact and ex1 and ex2
        rows.append(row)
    means = {src: {key: sum(r[src][key] for r in rows) / len(rows) for key in KEYS} for src in ("operator", "llm_whole")} if rows else None
    return {"n_tests": len(td["tests"]), "n_contributing": len(rows), "means": means, "exact": exact,
            "delta_lift": means["llm_whole"]["lift"] - means["operator"]["lift"] if means else None}


# --- task choice: structure only, before any value -----------------------------------------------

def choose(dets: dict, contributing: list[str]) -> list[tuple[str, str]]:
    feats = {}
    for t in contributing:
        td = task_data(dets[t])
        strata = list(td["tests"].values())
        feats[t] = {"goals": len(goals(td["detected"]["operator"])) + len(goals(td["detected"]["llm_whole"])),
                    "multi_model_classes": sum(len(c["models"]) >= 2 for c in td["classes"]),
                    "p_tests": strata.count("p"), "gen_tests": strata.count("gen")}
    picked: list[tuple[str, str]] = []
    rules = [("brute force: fewest goals", lambda t: (feats[t]["goals"], t)),
             ("cross-model rule: most multi-model classes", lambda t: (-feats[t]["multi_model_classes"], t)),
             ("stratified null: most P tests (with gen tests)",
              lambda t: (feats[t]["gen_tests"] == 0, -feats[t]["p_tests"], t))]
    for why, key in rules:
        t = min((x for x in contributing if x not in {p for p, _ in picked}), key=key)
        picked.append((t, f"{why} {feats[t]}"))
    return picked


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", type=Path, default=REPO / "results_tier2_ext" / "coupling" / "full")
    ap.add_argument("--tasks", nargs="*", help="override the fixed choice (not for the reported check)")
    args = ap.parse_args()
    spec = json.loads(FROZEN.read_text(encoding="utf-8"))["spec"]
    version, B = spec["version"], spec["null_permutations"]
    ends = {r["task"]: r for r in json.loads((args.run / "endpoints.json").read_text(encoding="utf-8"))["per_task"]}
    contributing = sorted(t for t, r in ends.items() if r.get("excluded") is None)
    dets = {t: json.loads((args.run / t / "detection.json").read_text(encoding="utf-8")) for t in contributing}
    picked = [(t, "override") for t in args.tasks] if args.tasks else choose(dets, contributing)
    ok_all = True
    for task, why in picked:
        print(f"\n=== {task}  ({why})")
        mine, theirs = recompute(dets[task], version, B), ends[task]
        tol = 1e-9 if mine["exact"] else 0.02
        checks = [("n_tests", mine["n_tests"], theirs["n_tests"], 0),
                  ("n_contributing", mine["n_contributing"], theirs["n_contributing"], 0),
                  ("delta_lift", mine["delta_lift"], theirs["delta_lift"], tol)]
        checks += [(f"{src}.{key}", mine["means"][src][key], theirs["means"][src][key], tol)
                   for src in ("operator", "llm_whole") for key in KEYS]
        print(f"  {'exact enumeration' if mine['exact'] else 'Monte Carlo above the limit'}; tolerance {tol}")
        for name, a, b, t in checks:
            ok = abs(a - b) <= t
            ok_all &= ok
            print(f"  {'OK ' if ok else 'BAD'} {name:22s} recomputed {a:.12g}   endpoints {b:.12g}")
    print("\nRESULT:", "all recomputed values agree" if ok_all else "MISMATCH -- stop and report")
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
