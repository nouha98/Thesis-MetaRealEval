"""Bounded witness search for RealClassEval mutants (extensions plan rev. 9, Stage 2).

Benchmark-specific by design (it builds class scenarios), so it lives under
``benchmarks/`` rather than ``stage0/``; the RQ code never imports it.

For one task:

1. **Pools.** The task's P scenarios (``extract_scenarios``; gate-excluded ones
   removed when the manifest is available) with per-step API flags from the
   contract (``contracts.api_flags``), and up to ``pool_size`` contract-valid
   generated scenarios (``strategies.generate_scenarios``).
2. **Reference baseline.** Each pool runs twice on the reference through the
   existing scenario runner in API mode. Differences between the two runs
   form the nondeterminism masks (API and full trace). Each scenario's domain
   is classified (D2): the reference completes, or raises an exception the
   contract documents for that call (valid); or it raises an undocumented
   exception at step u (``domain_uncertain`` from u on; earlier steps stay
   comparable); or it does not run (``reference_failed``).
3. **Per fault group** (one representative program): run both pools once,
   compare with the reference step by step. An API-visible difference on a
   valid step is a candidate witness (``api_value`` / ``api_exception``); a
   mutant timeout where the reference completes is ``nontermination``; an API
   difference only at or after an uncertain step is ``domain_uncertain``; a
   difference only in the historical full trace is ``private_state_only``.
4. **Shrink and replay.** The chosen scenario is truncated after the
   difference and shrunk deterministically (step deletion; for generated
   scenarios also argument simplification inside the contract) while a
   difference of the same level persists, then replayed in fresh processes
   (reference twice, mutant twice). Only a replayed difference counts.

Outcomes (D3 needs ``distinguished`` + ``api_visible`` + ``valid`` + replay):
``distinguished`` | ``unresolved`` | ``unsupported`` | ``timeout`` |
``invalid_artifact``. **No witness never means equivalent.**
"""

from __future__ import annotations

import ast
import time
from dataclasses import asdict, dataclass
from typing import Optional

from . import contracts as C
from .forkserver import run_scenarios
from .observe import api_diff, nondeterminism_mask
from .scenarios import UnsupportedScenario, _sut_alias, extract_scenarios
from .strategies import build_steps, generate_scenarios

GEN_ALIAS = "module_0"


@dataclass(frozen=True)
class WitnessSettings:
    pool_size: int = 40
    max_calls: int = 6
    timeout_s: float = 5.0
    mutant_budget_s: float = 300.0
    shrink_rounds: int = 6
    max_candidates_per_round: int = 16
    shrink_chunk: int = 4               # candidates per runner call; the budget is checked between chunks
    # import allowance before the per-scenario timeout. It is also the parent's backstop for a hang
    # the in-child watchdog cannot interrupt (e.g. catastrophic regex backtracking holds the GIL).
    import_allowance_s: float = 10.0
    seed: int = 20261112


# ---------------------------------------------------------------------------
# Pools and the reference baseline
# ---------------------------------------------------------------------------

def _p_pool(task, contract: dict, excluded: set[str]) -> tuple[str, str, list[dict]]:
    import ast as _ast
    header, scenarios = extract_scenarios(task.test_code, task.module_name)
    alias = _sut_alias(_ast.parse(task.test_code), task.module_name)
    pool = []
    for s in scenarios:
        if s.scenario_id in excluded:
            continue
        steps = [asdict(st) for st in s.steps]
        pool.append({"scenario_id": s.scenario_id, "steps": steps, "origin": "p_scenario", "xfail": s.xfail,
                     "api_flags": C.api_flags(steps, contract, alias)})
    return header, alias, pool


def _run(module: str, code: str, header: str, pool: list[dict], s: WitnessSettings, rules: dict) -> list[dict]:
    if not pool:
        return []
    clean = [{"scenario_id": p["scenario_id"], "steps": p["steps"], "api_flags": p["api_flags"]} for p in pool]
    return run_scenarios(module, code, header, clean, timeout_s=s.timeout_s, api_rules=rules,
                         import_allowance_s=s.import_allowance_s)


def _exc_simple_names(trace: dict, i: int) -> set[str]:
    tok = trace["tokens"].get(f"api:s{i}")
    if tok and tok[0] == "exc":
        return {n.split(".")[-1] for n in tok[1]}
    raw = trace["tokens"].get(f"s{i}", "")
    return {raw[4:].split(".")[-1]} if raw.startswith("EXC:") else set()


def classify_domain(scenario: dict, trace: dict, contract: dict, alias: str) -> dict:
    """D2 for one scenario from the reference's trace."""
    if trace["status"] != "ok":
        return {"domain": "reference_failed", "valid_prefix": 0, "uncertain_step": None,
                "reason": trace["status"]}
    for i, st in enumerate(scenario["steps"]):
        tok = trace["tokens"].get(f"s{i}")
        if tok is None:
            break
        if not tok.startswith("EXC:"):
            continue
        callee = C.step_callable(st["src"], alias, contract["class_name"])
        documented = C.documented_raises(contract, callee) if callee else set()
        if documented & _exc_simple_names(trace, i):
            if st["kind"] == "raises":
                continue                       # pytest.raises caught a documented exception
            return {"domain": "valid", "valid_prefix": i + 1, "uncertain_step": None,
                    "reason": "documented exception"}
        return {"domain": "domain_uncertain", "valid_prefix": i, "uncertain_step": i,
                "reason": f"reference raised undocumented {tok[4:]} in {callee or 'a non-contract step'}"}
    return {"domain": "valid", "valid_prefix": len(scenario["steps"]), "uncertain_step": None, "reason": "completed"}


def _masks(t1: dict, t2: dict) -> tuple[set[str], set[str], bool]:
    """(api mask, full mask, consistent status) between two reference runs."""
    if t1["status"] != t2["status"]:
        return set(), set(), False
    api1 = {k: v for k, v in t1["tokens"].items() if k.startswith("api:")}
    api2 = {k: v for k, v in t2["tokens"].items() if k.startswith("api:")}
    api_mask = {k for k in set(api1) | set(api2) if api1.get(k) != api2.get(k)}
    full1 = {k: v for k, v in t1["tokens"].items() if not k.startswith("api:")}
    full2 = {k: v for k, v in t2["tokens"].items() if not k.startswith("api:")}
    return api_mask, nondeterminism_mask(full1, full2), True


def prepare_task(task, contract: dict, settings: WitnessSettings, excluded: set[str] = frozenset(),
                 gated: bool = False) -> dict:
    """Everything shared by the task's fault groups (plain data, picklable for workers)."""
    rules = C.api_rules(contract)
    ctx = {"task": task.label, "module": task.module_name, "class_name": contract["class_name"],
           "reference": task.reference_code, "contract": contract, "rules": rules, "gated": gated,
           "settings": asdict(settings), "support": dict(contract["support"]), "pools": {}}
    if not contract["support"]["supported"]:
        return ctx
    try:
        p_header, p_alias, p_pool = _p_pool(task, contract, set(excluded))
    except UnsupportedScenario as e:
        ctx["support"] = {**ctx["support"], "supported": False,
                          "reasons": ctx["support"]["reasons"] + [f"P scenarios unsupported: {e}"]}
        return ctx
    gen_pool = generate_scenarios(contract, settings.pool_size, settings.seed, settings.max_calls)
    gen_header = f"import {task.module_name} as {GEN_ALIAS}\n"
    for name, header, alias, pool in (("p", p_header, p_alias, p_pool), ("gen", gen_header, GEN_ALIAS, gen_pool)):
        r1 = _run(task.module_name, task.reference_code, header, pool, settings, rules)
        r2 = _run(task.module_name, task.reference_code, header, pool, settings, rules)
        entries = []
        for sc, t1, t2 in zip(pool, r1, r2):
            api_mask, full_mask, consistent = _masks(t1, t2)
            dom = classify_domain(sc, t1, contract, alias) if consistent else \
                {"domain": "reference_nondeterministic", "valid_prefix": 0, "uncertain_step": None,
                 "reason": "reference status differs between runs"}
            entries.append({"scenario": sc, "ref": t1, "api_mask": sorted(api_mask),
                            "full_mask": sorted(full_mask), **dom})
        ctx["pools"][name] = {"header": header, "alias": alias, "entries": entries}
    p_ok = sum(e["domain"] in ("valid", "domain_uncertain") and e["valid_prefix"] > 0 for e in ctx["pools"]["p"]["entries"])
    all_entries = ctx["pools"]["p"]["entries"] + ctx["pools"]["gen"]["entries"]
    nondet = sum(e["domain"] == "reference_nondeterministic" for e in all_entries)
    valid = sum(e["domain"] == "valid" for e in all_entries)
    runtime_reasons = []
    if p_ok == 0:
        runtime_reasons.append("no P scenario runs on the reference")
    if valid == 0:
        runtime_reasons.append("no scenario is in the valid domain on the reference")
    ctx["runtime"] = {"p_scenarios": len(p_pool), "p_scenarios_running": p_ok,
                      "generated": len(gen_pool), "valid_scenarios": valid,
                      "domain_uncertain_scenarios": sum(e["domain"] == "domain_uncertain" for e in all_entries),
                      "reference_failed": sum(e["domain"] == "reference_failed" for e in all_entries),
                      "reference_nondeterministic": nondet,
                      "api_masked_keys": sum(len(e["api_mask"]) for e in all_entries)}
    if runtime_reasons:
        ctx["support"] = {**ctx["support"], "supported": False,
                          "reasons": ctx["support"]["reasons"] + runtime_reasons}
    return ctx


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare(entry: dict, cand: dict, rules: dict) -> dict:
    """API-level and full-trace comparison of a candidate trace with the reference entry."""
    ref, sc = entry["ref"], entry["scenario"]
    out = {"api": None, "full_differs": False, "nontermination": False, "import_error": False}
    if entry["domain"] in ("reference_failed", "reference_nondeterministic"):
        return out
    if cand["status"] == "import_error":
        out["import_error"] = True
        return out
    if cand["status"] == "timeout":
        out["nontermination"] = True
        out["nontermination_domain"] = "valid" if entry["domain"] == "valid" else "domain_uncertain"
        return out
    if cand["status"] == "crashed":
        out["api"] = {"step": None, "kind": "api_exception", "detail": f"crashed: {cand['tokens'].get('crash')}",
                      "domain": "valid" if entry["valid_prefix"] > 0 else "domain_uncertain"}
        return out
    api_mask, flags = set(entry["api_mask"]), sc["api_flags"]
    u = entry["uncertain_step"]
    for i in range(len(sc["steps"])):
        key = f"api:s{i}"
        if f"s{i}" not in ref["tokens"] and f"s{i}" not in cand["tokens"]:
            break
        if not (i < len(flags) and flags[i]):
            rt, ct = ref["tokens"].get(f"s{i}"), cand["tokens"].get(f"s{i}")
            if (rt is None) != (ct is None) or (rt or "").startswith("EXC:") != (ct or "").startswith("EXC:"):
                break                           # one side stopped/raised at a non-API step: not attributable
            continue
        if key in api_mask:
            continue
        r, c = ref["tokens"].get(key), cand["tokens"].get(key)
        d = api_diff(r, c, rules, where=f"s{i}")
        if d:
            exc = (r is not None and r[0] == "exc") or (c is not None and c[0] == "exc") or c is None
            out["api"] = {"step": i, "kind": "api_exception" if exc else "api_value", "detail": d,
                          "domain": "valid" if i < entry["valid_prefix"] else "domain_uncertain"}
            break
        if u is not None and i >= u:
            break
    full_mask = set(entry["full_mask"])
    rk = {k for k in ref["tokens"] if not k.startswith("api:")}
    ck = {k for k in cand["tokens"] if not k.startswith("api:")}
    out["full_differs"] = any(ref["tokens"].get(k) != cand["tokens"].get(k) for k in (rk | ck) - full_mask)
    return out


# ---------------------------------------------------------------------------
# Shrinking and replay
# ---------------------------------------------------------------------------

def _names(src: str) -> set[str]:
    try:
        return {n.id for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Name)}
    except SyntaxError:
        return set()


def _deletion_candidates(sc: dict, upto: int) -> list[dict]:
    """Truncate after step ``upto``; then each single deletion of an earlier step whose bound name is
    not used later (the constructor of a generated scenario is never deleted)."""
    steps, flags = sc["steps"][:upto + 1], sc["api_flags"][:upto + 1]
    out = [{**sc, "steps": steps, "api_flags": flags}]
    if sc.get("meta"):
        calls = sc["meta"]["calls"][:max(upto, 1)]
        out = [{**sc, "meta": {**sc["meta"], "calls": calls}}]
        for j in range(len(calls)):
            if len(calls) > 1:
                out.append({**sc, "meta": {**sc["meta"], "calls": calls[:j] + calls[j + 1:]}})
        return out
    for j in range(len(steps)):
        if len(steps) == 1:
            break
        tgt = steps[j].get("target")
        if tgt and any(tgt in _names(s["src"]) for s in steps[j + 1:]):
            continue
        out.append({**sc, "steps": steps[:j] + steps[j + 1:], "api_flags": flags[:j] + flags[j + 1:]})
    return out


_SIMPLE = {"int": [0, 1], "float": [0.0, 1.0], "str": ["", "a"], "bool": [False, True], "bytes": [b""],
           "list": [[]], "set": [set()], "dict": [{}], "none": [None], "tuple": [()]}


def _param_list(contract: dict, callable_name: str) -> list[dict]:
    if callable_name == "__init__":
        return contract["constructor"]["params"]
    return contract["methods"].get(callable_name, {}).get("params", [])


def _simplify_candidates(sc: dict, contract: dict) -> list[dict]:
    meta = sc.get("meta")
    if not meta:
        return []
    out = []
    calls = [("__init__", meta["ctor"], None)] + [(c["callable"], c, i) for i, c in enumerate(meta["calls"])]
    for name, call, idx in calls:
        params = [p for p in _param_list(contract, name) if p["kind"] in ("positional", "keyword_only")]
        for pos, value in enumerate(call["args"]):
            p = params[pos] if pos < len(params) else None
            for simple in _simple_values(p):
                if simple == value or not C.value_ok(simple, p["type"], p.get("constraints")):
                    continue
                new_call = {**call, "args": call["args"][:pos] + [simple] + call["args"][pos + 1:]}
                out.append(_with_call(sc, contract, idx, new_call))
        for k, value in call["kwargs"].items():
            p = next((q for q in params if q["name"] == k), None)
            for simple in _simple_values(p):
                if simple == value or (p and not C.value_ok(simple, p["type"], p.get("constraints"))):
                    continue
                out.append(_with_call(sc, contract, idx, {**call, "kwargs": {**call["kwargs"], k: simple}}))
    return out


def _simple_values(p: Optional[dict]) -> list:
    if p is None:
        return []
    t = p["type"]["t"]
    opts = [o["t"] for o in p["type"]["options"]] if t == "union" else [t]
    vals = []
    for o in opts:
        vals += _SIMPLE.get(o, [])
    return vals


def _with_call(sc: dict, contract: dict, idx: Optional[int], call: dict) -> dict:
    meta = sc["meta"]
    new_meta = {"ctor": call, "calls": meta["calls"]} if idx is None else \
        {"ctor": meta["ctor"], "calls": meta["calls"][:idx] + [call] + meta["calls"][idx + 1:]}
    return {**sc, "meta": new_meta}


def _materialise(sc: dict, contract: dict) -> dict:
    if sc.get("meta"):
        steps = build_steps(contract, sc["meta"]["ctor"], sc["meta"]["calls"], GEN_ALIAS)
        return {**sc, "steps": steps, "api_flags": [True] * len(steps)}
    return sc


def _size(sc: dict) -> tuple[int, int]:
    return len(sc["steps"]), sum(len(s["src"]) for s in sc["steps"])


def _level_of(cmp: dict) -> Optional[tuple[str, str]]:
    """(level, domain) of a comparison result, strongest first."""
    if cmp["api"] and cmp["api"]["domain"] == "valid":
        return "api_visible", "valid"
    if cmp["nontermination"] and cmp.get("nontermination_domain") == "valid":
        return "nontermination", "valid"
    if cmp["api"]:
        return "api_visible", "domain_uncertain"
    if cmp["nontermination"]:
        return "nontermination", "domain_uncertain"
    if cmp["full_differs"]:
        return "private_state_only", "valid"
    return None


def _evaluate(ctx: dict, pool_name: str, scs: list[dict], code: str, s: WitnessSettings) -> list[tuple[dict, dict, Optional[tuple]]]:
    """Run candidate scenarios on reference (once) and mutant; classify; compare."""
    pool = ctx["pools"][pool_name]
    scs = [_materialise(x, ctx["contract"]) for x in scs]
    refs = _run(ctx["module"], ctx["reference"], pool["header"], scs, s, ctx["rules"])
    cands = _run(ctx["module"], code, pool["header"], scs, s, ctx["rules"])
    out = []
    for sc, r, c in zip(scs, refs, cands):
        entry = {"scenario": sc, "ref": r, "api_mask": [], "full_mask": [],
                 **classify_domain(sc, r, ctx["contract"], pool["alias"])}
        cmp = compare(entry, c, ctx["rules"])
        out.append((sc, cmp, _level_of(cmp)))
    return out


def _shrink(ctx: dict, pool_name: str, sc: dict, cmp: dict, target: tuple, code: str,
            s: WitnessSettings, deadline: float) -> tuple[dict, dict, int]:
    """Greedy deterministic shrinking while a difference at level ``target`` persists."""
    best, best_cmp, rounds = sc, cmp, 0
    upto = cmp["api"]["step"] if cmp["api"] and cmp["api"]["step"] is not None else len(sc["steps"]) - 1
    while rounds < s.shrink_rounds and time.monotonic() < deadline:
        rounds += 1
        base = _size(_materialise(best, ctx["contract"]))
        cands = _deletion_candidates(best, upto) + _simplify_candidates(best, ctx["contract"])
        # strictly smaller (fewer steps, then shorter source): shrinking always terminates
        cands = [c for c in cands if _size(_materialise(c, ctx["contract"])) < base]
        cands = cands[: s.max_candidates_per_round]
        if not cands:
            break
        results = []
        for k in range(0, len(cands), s.shrink_chunk):        # bounded: budget checked between chunks
            if time.monotonic() >= deadline:
                break
            results += [(x, c, lvl) for x, c, lvl in _evaluate(ctx, pool_name, cands[k:k + s.shrink_chunk], code, s)
                        if lvl == target]
        if not results:
            break
        x, c, _ = min(results, key=lambda t: _size(t[0]))
        best, best_cmp = x, c
        upto = c["api"]["step"] if c["api"] and c["api"]["step"] is not None else len(x["steps"]) - 1
    return best, best_cmp, rounds


def _replay(ctx: dict, pool_name: str, sc: dict, target: tuple, code: str, s: WitnessSettings) -> dict:
    """Fresh processes: reference twice (masks), mutant twice; the target difference must recur."""
    pool = ctx["pools"][pool_name]
    r1 = _run(ctx["module"], ctx["reference"], pool["header"], [sc], s, ctx["rules"])[0]
    r2 = _run(ctx["module"], ctx["reference"], pool["header"], [sc], s, ctx["rules"])[0]
    api_mask, full_mask, consistent = _masks(r1, r2)
    entry = {"scenario": sc, "ref": r1, "api_mask": sorted(api_mask), "full_mask": sorted(full_mask),
             **classify_domain(sc, r1, ctx["contract"], pool["alias"])}
    levels = []
    for _ in range(2):
        c = _run(ctx["module"], code, pool["header"], [sc], s, ctx["rules"])[0]
        levels.append(_level_of(compare(entry, c, ctx["rules"])))
    return {"confirmed": consistent and all(lv == target for lv in levels), "reference_consistent": consistent,
            "levels": [list(lv) if lv else None for lv in levels]}


# ---------------------------------------------------------------------------
# One fault group
# ---------------------------------------------------------------------------

_RANK = {("api_visible", "valid"): 0, ("nontermination", "valid"): 1, ("api_visible", "domain_uncertain"): 2,
         ("nontermination", "domain_uncertain"): 3, ("private_state_only", "valid"): 4}


def search_group(ctx: dict, group_id: str, code: Optional[str]) -> dict:
    """Witness search for one fault group's representative program (runs in a worker)."""
    s = WitnessSettings(**ctx["settings"])
    t0 = time.monotonic()
    deadline = t0 + s.mutant_budget_s
    rec = {"group_id": group_id, "outcome": None, "level": None, "kind": None, "domain": None, "origin": None,
           "witness": None, "replay": None, "counts": {}, "seconds": None}

    def done(outcome: str, **kw) -> dict:
        rec.update(outcome=outcome, **kw)
        rec["seconds"] = round(time.monotonic() - t0, 2)
        return rec

    if not ctx["support"]["supported"]:
        return done("unsupported", reason="; ".join(ctx["support"]["reasons"]))
    if code is None:
        return done("invalid_artifact", reason="mutant is not a runnable class module")
    found, counts = [], {"scenarios_run": 0, "valid_scenarios": 0, "domain_uncertain_scenarios": 0,
                         "api_difference_scenarios": 0, "full_only_scenarios": 0, "import_errors": 0}
    for pool_name in ("p", "gen"):
        pool = ctx["pools"][pool_name]
        # a scenario the reference cannot run (or runs nondeterministically) can never give a witness
        entries = [e for e in pool["entries"] if e["domain"] in ("valid", "domain_uncertain")]
        if not entries:
            continue
        cands = _run(ctx["module"], code, pool["header"], [e["scenario"] for e in entries], s, ctx["rules"])
        for e, c in zip(entries, cands):
            counts["scenarios_run"] += 1
            counts["valid_scenarios"] += e["domain"] == "valid"
            counts["domain_uncertain_scenarios"] += e["domain"] == "domain_uncertain"
            cmp = compare(e, c, ctx["rules"])
            counts["import_errors"] += cmp["import_error"]
            counts["api_difference_scenarios"] += bool(cmp["api"])
            counts["full_only_scenarios"] += bool(cmp["full_differs"] and not cmp["api"] and not cmp["nontermination"])
            lvl = _level_of(cmp)
            if lvl:
                found.append((_RANK[lvl], _size(e["scenario"]), pool_name, e["scenario"], cmp, lvl))
        if time.monotonic() > deadline:
            rec["counts"] = counts
            return done("timeout", reason="budget exhausted before every scenario ran")
    rec["counts"] = counts
    running = counts["scenarios_run"] - counts["import_errors"]
    if counts["scenarios_run"] and running == 0:
        return done("invalid_artifact", reason="mutant fails to import on every scenario")
    if not found:
        return done("unresolved", reason="no difference within budget (not an equivalence certificate)")
    found.sort(key=lambda f: (f[0], f[1]))
    for _, _, pool_name, sc, cmp, lvl in found[:3]:
        if time.monotonic() > deadline:
            return done("timeout", reason="budget exhausted while shrinking/replaying")
        shrunk, scmp, rounds = _shrink(ctx, pool_name, sc, cmp, lvl, code, s, deadline)
        shrunk = _materialise(shrunk, ctx["contract"])
        replay = _replay(ctx, pool_name, shrunk, lvl, code, s)
        if not replay["confirmed"] and shrunk is not sc:
            replay = _replay(ctx, pool_name, _materialise(sc, ctx["contract"]), lvl, code, s)
            if replay["confirmed"]:
                shrunk, scmp = _materialise(sc, ctx["contract"]), cmp
        if replay["confirmed"]:
            level, domain = lvl
            kind = "nontermination" if level == "nontermination" else \
                (scmp["api"]["kind"] if scmp.get("api") else None)
            return done("distinguished", level="api_visible" if level in ("api_visible", "nontermination") else level,
                        kind=kind, domain=domain, origin="p_scenario" if pool_name == "p" else "generated",
                        witness={"scenario_id": shrunk["scenario_id"], "steps": shrunk["steps"],
                                 "api_flags": shrunk["api_flags"], "difference": scmp.get("api"),
                                 "original_steps": len(sc["steps"]), "shrink_rounds": rounds},
                        replay=replay)
    return done("unresolved", reason="differences found but none replayed (not an equivalence certificate)")
