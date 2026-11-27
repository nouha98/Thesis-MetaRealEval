"""A2: non-agent, reference-differential hidden tests (plan rev. 9.3, Stage 4).

For one task:

1. **Pool, disjoint from the witness search.** Contract-valid scenarios from the Stage 2
   strategies with the A2 seed (``a2_base_seed``), minus every scenario the witness search's own
   generated pool contains (exact step match): A2 never reuses the scenarios that confirmed the
   faults it is later evaluated on.
2. **Reference baseline.** Each scenario runs twice on the reference in API mode (masks for
   nondeterministic keys); only valid-domain steps (D2) are asserted.
3. **Kills.** Each *discovery* fault group (primary confirmed, D3) runs on the pool; a kill is an
   API-visible difference on a valid step (``witness.compare``). Nontermination is not a kill
   (an emitted test would only time out).
4. **Greedy minimisation.** Pick the scenario killing most uncovered discovery groups (ties:
   smaller scenario, then pool order), up to ``max_tests``. Tests that kill nothing are not kept.
5. **Emission.** ``test_h_<i>`` functions replay the steps with ``forkserver._run_scenario`` in API
   mode and compare each expected API token with ``observe.api_diff`` under the contract's rules:
   assertions are only on D1 API observations, never ``repr``/private state.

The emitted code is appended to the P test file for grading (``DegradedSuite(test_code=P+H,
extra_valid=H, subset=H)``), exactly like RQ4's ``test_ca_<i>``.

**Output specification (rule R7, decisions 10.2).** A completion is written from the skeleton
docstrings only, so H may assert only what they specify. Each public callable has a reviewed level
(``config/extensions_protocol/output_spec_v1.json``): ``value`` (the docstring determines the value:
asserted as before), ``type`` (only the kind is promised: the type family is asserted), ``none``
(nothing is promised: only "returns normally" is asserted). Exception tokens are always asserted
(valid-domain exceptions are documented ones, D2), and a completion that raises where the reference
returns is detected at every level. The restriction applies to the kill matrix (test selection) and
to the emitted assertions alike. Constructors are always ``value`` (an opaque object or an exception).
"""

from __future__ import annotations

import ast
import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Optional

from ..benchmarks.contracts import api_rules, step_callable
from ..benchmarks.strategies import generate_scenarios
from ..benchmarks.witness import GEN_ALIAS, WitnessSettings, _masks, _materialise, _run, _size, classify_domain
from .spec import DEFAULT_LEVEL, LEVELS, restrict, spec_diff, type_family  # noqa: F401  (re-exported)

def step_name(src: str, alias: str, class_name: str) -> Optional[str]:
    """The callable or property a step uses (``step_callable`` plus plain attribute reads)."""
    try:
        node = ast.parse(src, mode="eval").body
    except SyntaxError:
        return None
    # the strategies call these protocol methods through the builtin (strategies.call_src): repr(obj) etc.
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _PROTOCOL_BUILTINS
            and len(node.args) == 1 and not node.keywords):
        return _PROTOCOL_BUILTINS[node.func.id]
    name = step_callable(src, alias, class_name)
    if name is not None:
        return name
    return node.attr if isinstance(node, ast.Attribute) else None


_PROTOCOL_BUILTINS = {"repr": "__repr__", "str": "__str__", "len": "__len__"}


def level_of(levels: dict, name: Optional[str]) -> str:
    """Constructors are ``value``; an unrecognised step gets the default level, never ``value``."""
    if name == "__init__":
        return "value"
    return levels.get(name, DEFAULT_LEVEL)


@dataclass(frozen=True)
class A2Settings:
    pool_size: int = 100
    max_calls: int = 6
    max_tests: int = 20
    cover_k: int = 1               # tuned on development tasks only (plan D5); 1 = plain set cover
    timeout_s: float = 5.0
    import_allowance_s: float = 10.0

    def witness_settings(self) -> WitnessSettings:
        return WitnessSettings(pool_size=self.pool_size, max_calls=self.max_calls, timeout_s=self.timeout_s,
                               import_allowance_s=self.import_allowance_s)


def a2_base_seed(extension_seed: int) -> int:
    """A base seed for A2 that differs from the witness search's (the extension seed itself)."""
    return int(hashlib.sha256(f"{extension_seed}|a2".encode()).hexdigest()[:8], 16)


def _key(sc: dict) -> tuple:
    return tuple(st["src"] for st in sc["steps"])


def a2_pool(contract: dict, settings: A2Settings, extension_seed: int, witness_pool_size: int,
            witness_max_calls: int) -> tuple[list[dict], int]:
    """(A2 scenarios, number dropped because the witness pool contains them)."""
    witness = {_key(_materialise(s, contract)) for s in
               generate_scenarios(contract, witness_pool_size, extension_seed, witness_max_calls)}
    pool = [_materialise(s, contract) for s in
            generate_scenarios(contract, settings.pool_size, a2_base_seed(extension_seed), settings.max_calls)]
    kept = [s for s in pool if _key(s) not in witness]
    for i, s in enumerate(kept):
        s["scenario_id"] = f"a2_{i}"
    return kept, len(pool) - len(kept)


def reference_entries(module: str, reference: str, contract: dict, pool: list[dict],
                      s: WitnessSettings) -> list[dict]:
    """Two reference runs per scenario -> entries usable by ``witness.compare`` (valid domain only)."""
    header = f"import {module} as {GEN_ALIAS}\n"
    rules = api_rules(contract)
    r1 = _run(module, reference, header, pool, s, rules)
    r2 = _run(module, reference, header, pool, s, rules)
    out = []
    for sc, t1, t2 in zip(pool, r1, r2):
        api_mask, full_mask, consistent = _masks(t1, t2)
        if not consistent:
            continue
        dom = classify_domain(sc, t1, contract, GEN_ALIAS)
        if dom["domain"] != "valid" or dom["valid_prefix"] == 0:
            continue
        out.append({"scenario": sc, "ref": t1, "api_mask": sorted(api_mask), "full_mask": sorted(full_mask), **dom})
    return out


def restrict_fields(tok, levels: dict):
    """H v1.1 Fix A (decisions 10.8): the fields of an own-class object token kept at ``value`` level are
    restricted by their own R7 entry; a field without an entry (a plain attribute) is not asserted."""
    if not tok or tok[0] != "obj":
        return tok
    fields = {}
    for name, ft in tok[2].items():
        base = name[:-2] if name.endswith("()") else name
        if base in levels and base != "__init__":
            r = restrict(ft, levels[base])
            fields[name] = restrict_fields(r, levels) if levels[base] == "value" else r
    return ["obj", tok[1], fields]


def expected_tokens(entry: dict, levels: Optional[dict] = None, class_name: str = "", fix_a: bool = False) -> dict:
    """API tokens a test asserts: flagged valid-prefix steps the reference recorded, minus masked keys,
    each restricted by its callable's specification level (``levels=None``: every output is ``value``).
    ``fix_a`` (H v1.1 only): object fields follow their own levels (``restrict_fields``)."""
    sc, ref, mask = entry["scenario"], entry["ref"]["tokens"], set(entry["api_mask"])
    exp = {}
    for i in range(entry["valid_prefix"]):
        k = f"api:s{i}"
        if sc["api_flags"][i] and k in ref and k not in mask:
            lvl = "value" if levels is None else level_of(levels, step_name(sc["steps"][i]["src"], GEN_ALIAS, class_name))
            exp[k] = restrict(ref[k], lvl)
            if fix_a and levels is not None and lvl == "value":
                exp[k] = restrict_fields(exp[k], levels)
    return exp


def kills_of(exp: dict, cand: dict, rules: dict) -> bool:
    """Would the emitted test fail on this candidate trace? (a timeout or import error is not counted)"""
    if cand["status"] in ("timeout", "import_error"):
        return False
    if cand["status"] == "crashed":
        return True
    return any(spec_diff(v, cand["tokens"].get(k), rules, where=k) for k, v in exp.items())


def kill_matrix(module: str, contract: dict, entries: list[dict], discovery: dict[str, Optional[str]],
                s: WitnessSettings, levels: Optional[dict] = None) -> dict[str, set[str]]:
    """{scenario_id: discovery group ids it kills} under the same restricted comparison the test will use."""
    header = f"import {module} as {GEN_ALIAS}\n"
    rules = api_rules(contract)
    kills: dict[str, set[str]] = {e["scenario"]["scenario_id"]: set() for e in entries}
    exps = {e["scenario"]["scenario_id"]: expected_tokens(e, levels, contract["class_name"]) for e in entries}
    for gid, code in sorted(discovery.items()):
        if code is None or not entries:
            continue
        cands = _run(module, code, header, [e["scenario"] for e in entries], s, rules)
        for e, c in zip(entries, cands):
            if kills_of(exps[e["scenario"]["scenario_id"]], c, rules):
                kills[e["scenario"]["scenario_id"]].add(gid)
    return kills


def greedy_select(entries: list[dict], kills: dict[str, set[str]], max_tests: int, cover_k: int = 1) -> list[dict]:
    """Greedy multi-cover: each killable discovery group is killed by up to ``cover_k`` distinct tests
    (``cover_k = 1`` is plain set cover). Ties: smaller scenario, then pool order."""
    order = {e["scenario"]["scenario_id"]: i for i, e in enumerate(entries)}
    left = [e for e in entries if kills[e["scenario"]["scenario_id"]] and expected_tokens(e)]
    demand = {g: cover_k for e in left for g in kills[e["scenario"]["scenario_id"]]}
    chosen = []
    while left and len(chosen) < max_tests:
        def gain(e):
            return sum(demand[g] > 0 for g in kills[e["scenario"]["scenario_id"]])
        best = min(left, key=lambda e: (-gain(e), _size(e["scenario"]), order[e["scenario"]["scenario_id"]]))
        if not gain(best):
            break
        chosen.append(best)
        for g in kills[best["scenario"]["scenario_id"]]:
            demand[g] = max(0, demand[g] - 1)
        left.remove(best)
    return chosen


def _lit(obj) -> str:
    """A Python expression rebuilding ``obj`` from JSON (safe for every token, incl. inf/nan)."""
    return f"_h_json.loads({json.dumps(obj)!r})"


def emit(task_id: str, module: str, contract: dict, tests: list[dict]) -> str:
    """Pytest source for the selected tests (appended to the P file for grading)."""
    rules = api_rules(contract)
    blocks = []
    for i, t in enumerate(tests):
        blocks.append(
            f"def test_h_{i}():\n"
            f"    _steps = {_lit(t['steps'])}\n"
            f"    _trace = _h_run(_steps, dict(globals()), api={{'flags': {_lit(t['api_flags'])}, 'rules': _H_RULES}})\n"
            f"    _expected = {_lit(t['expected'])}\n"
            f"    _diffs = [d for d in (_h_diff(v, _trace.get(k), _H_RULES, k) for k, v in _expected.items()) if d]\n"
            f"    assert not _diffs, {('A2 hidden test ' + t['scenario_id'] + ': %r')!r} % _diffs\n")
    head = (f"# A2 hidden tests for {task_id}: reference-differential, API observations only (plan rev. 9.3)\n"
            f"import json as _h_json\n"
            f"import {module} as {GEN_ALIAS}\n"
            f"from meta_real_eval.benchmarks.forkserver import _run_scenario as _h_run\n"
            f"from meta_real_eval.oracles.spec import spec_diff as _h_diff\n"
            f"_H_RULES = {_lit(rules)}\n\n\n")
    code = head + "\n\n".join(blocks)
    compile(code, "<a2_hidden_tests>", "exec")
    return code


def build_a2(task_id: str, module: str, reference: str, contract: dict, discovery: dict[str, Optional[str]],
             settings: A2Settings, extension_seed: int, witness_settings: WitnessSettings,
             levels: Optional[dict] = None) -> dict:
    """Everything A2 decides for one task (before admission). ``levels``: the R7 output specification
    ({callable: value|type|none}); None asserts every output as ``value`` (no specification)."""
    s = settings.witness_settings()
    pool, dropped = a2_pool(contract, settings, extension_seed, witness_settings.pool_size, witness_settings.max_calls)
    entries = reference_entries(module, reference, contract, pool, s)
    kills = kill_matrix(module, contract, entries, discovery, s, levels)
    chosen = greedy_select(entries, kills, settings.max_tests, settings.cover_k)
    tests = [{"name": f"test_h_{i}", "scenario_id": e["scenario"]["scenario_id"], "steps": e["scenario"]["steps"],
              "api_flags": e["scenario"]["api_flags"], "expected": expected_tokens(e, levels, contract["class_name"]),
              "kills": sorted(kills[e["scenario"]["scenario_id"]])} for i, e in enumerate(chosen)]
    killable = set().union(*kills.values()) if kills else set()
    used = {step_name(st["src"], GEN_ALIAS, contract["class_name"]) for t in tests for st in t["steps"]}
    defaulted = sorted(n for n in used if n not in (None, "__init__") and levels is not None and n not in levels)
    return {"task": task_id, "settings": asdict(settings), "a2_base_seed": a2_base_seed(extension_seed),
            "output_levels": levels, "levels_defaulted": defaulted,
            "pool": {"generated": len(pool) + dropped, "dropped_in_witness_pool": dropped, "valid": len(entries)},
            "discovery_groups": sorted(discovery), "killed_by_pool": sorted(killable),
            "covered_by_tests": sorted(set().union(*(set(t["kills"]) for t in tests)) if tests else set()),
            "tests": tests}
