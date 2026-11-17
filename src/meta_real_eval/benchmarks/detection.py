"""Detection matrices for Stage 2b coupling (protocol_freeze_decisions.md section 9.1).

Benchmark-specific (class scenarios), so it lives next to ``witness.py`` and reuses its pool
construction, reference baseline and comparison unchanged.

* **Primary pool**: the witness pools (P scenarios + generated contract-valid scenarios); a test
  is a scenario whose reference is consistent across two runs and whose domain is ``valid``.
  A program detects a test iff ``witness._level_of(witness.compare(...))`` is an API-visible or
  nontermination difference in the valid domain.
* **Perturbed-P pool**: the Stage 0 / RQ3 pool through the ``ScenarioProvider`` methods, compared
  only on observable values (:func:`observable_keys`): the results of ``observe`` / ``raises``
  steps whose tokens contain builtin types only, or exception types. End-of-scenario snapshots,
  ``exec`` steps and own-class / opaque values are never compared -- independently written
  solutions structure their state differently, so comparing it would flag every solution.

Every program runs twice; a cell is ``detect`` / ``same`` when both runs agree, else ``masked``.
"""

from __future__ import annotations

import re
from typing import Optional

from .observe import is_opaque
from .witness import WitnessSettings, _level_of, _run, compare, prepare_task

DETECT_LEVELS = {("api_visible", "valid"), ("nontermination", "valid")}
_TYPE_RE = re.compile(r"VALUE:([A-Za-z_][\w.]*):")


def prepare_primary(task, contract: dict, n_generated: int, seed: int, excluded=frozenset(), gated=False,
                    timeout_s: float = 5.0, max_calls: int = 6) -> dict:
    settings = WitnessSettings(pool_size=n_generated, seed=seed, timeout_s=timeout_s, max_calls=max_calls)
    ctx = prepare_task(task, contract, settings, excluded, gated)
    tests = {}
    for pool_name, pool in ctx.get("pools", {}).items():
        for e in pool["entries"]:
            if e["domain"] == "valid":
                tests[f"{pool_name}:{e['scenario']['scenario_id']}"] = pool_name
    ctx["tests"] = tests
    return ctx


def _primary_once(ctx: dict, code: str) -> tuple[dict[str, bool], bool, dict[str, str]]:
    s = WitnessSettings(**ctx["settings"])
    hits, details, import_error = {}, {}, False
    for pool_name, pool in ctx["pools"].items():
        entries = [e for e in pool["entries"] if e["domain"] == "valid"]
        if not entries:
            continue
        cands = _run(ctx["module"], code, pool["header"], [e["scenario"] for e in entries], s, ctx["rules"])
        for e, c in zip(entries, cands):
            tid = f"{pool_name}:{e['scenario']['scenario_id']}"
            cmp = compare(e, c, ctx["rules"])
            import_error |= cmp["import_error"]
            hit = _level_of(cmp) in DETECT_LEVELS
            hits[tid] = hit
            if hit and pool_name == "p" and cmp.get("api"):
                details[tid] = str(cmp["api"].get("detail"))[:300]
    return hits, import_error, details


def primary_cells(ctx: dict, code: Optional[str], runs: int = 2) -> dict:
    """{"detect": [...], "masked": [...], "import_error": bool, "p_details": {test: diff}}."""
    if code is None or not ctx["support"]["supported"]:
        return {"detect": [], "masked": [], "import_error": code is None, "p_details": {}}
    results = [_primary_once(ctx, code) for _ in range(runs)]
    tests = sorted(ctx["tests"])
    detect = [t for t in tests if all(r[0].get(t) for r in results)]
    masked = [t for t in tests if len({bool(r[0].get(t)) for r in results}) > 1]
    return {"detect": detect, "masked": masked, "import_error": all(r[1] for r in results),
            "p_details": {t: results[0][2][t] for t in detect if t in results[0][2]}}


# ---------------------------------------------------------------------------
# Perturbed-P pool
# ---------------------------------------------------------------------------

def _builtin_only(tok: str) -> bool:
    if tok.startswith(("EXC:", "NO_EXC:")):
        tok = tok.split(":", 1)[1] if tok.startswith("NO_EXC:") else ""
    if not tok:
        return True
    if is_opaque(tok):
        return False
    return all(t.startswith("builtins.") for t in _TYPE_RE.findall(tok))


def observable_keys(scenario, ref_tokens: dict, mask: frozenset) -> list[str]:
    keys = []
    for i, st in enumerate(scenario.steps):
        k = f"s{i}"
        if st.kind not in ("observe", "raises") or k in mask or k not in ref_tokens:
            continue
        if _builtin_only(ref_tokens[k]):
            keys.append(k)
    return keys


def prepare_perturbed(bench, task, n_items: int, seed: int, timeout_s: float) -> dict:
    pool = bench.input_pool(task, n_items, seed)
    refs, masks = bench.reference_observations(task, pool, timeout_s)
    tests = {}
    for i, (sc, r, m) in enumerate(zip(pool.items, refs, masks)):
        if r["status"] == "ok":
            keys = observable_keys(sc, r["tokens"], m)
            if keys:
                tests[f"x:{sc.scenario_id}"] = {"index": i, "keys": keys}
    return {"pool": pool, "refs": refs, "tests": tests, "timeout_s": timeout_s}


def _perturbed_once(bench, task, pctx: dict, code: str) -> dict[str, bool]:
    obs = bench.observe(task, code, pctx["pool"], pctx["timeout_s"])
    hits = {}
    for tid, t in pctx["tests"].items():
        ref, cand = pctx["refs"][t["index"]]["tokens"], obs[t["index"]]
        if cand["status"] in ("timeout", "import_error"):
            hits[tid] = cand["status"] == "timeout"
            continue
        hits[tid] = any(cand["tokens"].get(k) != ref[k] for k in t["keys"])
    return hits


def perturbed_cells(bench, task, pctx: dict, code: Optional[str], runs: int = 2) -> dict:
    if code is None or not pctx["tests"]:
        return {"detect": [], "masked": [], "import_error": code is None}
    results = [_perturbed_once(bench, task, pctx, code) for _ in range(runs)]
    tests = sorted(pctx["tests"])
    return {"detect": [t for t in tests if all(r[t] for r in results)],
            "masked": [t for t in tests if len({r[t] for r in results}) > 1], "import_error": False}
