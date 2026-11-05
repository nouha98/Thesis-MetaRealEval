"""Tier 2 adapter: RealClassEval behind the :mod:`.base` contract.

Data comes from two files (see the Tier 2 plan, M0):

``data/realclasseval/realclasseval_v1.jsonl.gz``  the staged corpus, one row
    per joinable task (``scripts/fetch_realclasseval.py``).
``data/realclasseval/manifest_v1.json``  the M0 validity gate's verdicts
    (``scripts/validate_realclasseval.py``): which tasks are accepted, their
    contiguous ``task_index`` (what a SLURM array indexes), and per test the
    D2 class (``valid_behavioural`` / ``valid_exception_oracle`` / invalid_*),
    the reference's exception type, and the ``trivial`` flag.

:meth:`RealClassEvalBenchmark.load_tasks` only ever returns gate-accepted
tasks; scoring needs the gate's verdicts, so it refuses to run without a
manifest. The gate itself reads the raw corpus via :meth:`corpus_tasks`.

D7 import policy (:func:`build_solution_with_report`): only import
statements present in the prompt the model saw may be re-attached to a
completion. Nothing is ever copied from the reference module. M0 found that
no skeleton in the corpus contains a top-level import, so in practice
nothing is re-attached -- the paper's own protocol -- but the three import
sets are still recorded per completion so the audit can show it.
"""

from __future__ import annotations

import ast
import gzip
import json
import logging
import math
import random
import re
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

from ..core.sandbox import execute_pytest
from ..rq2.evaluator import _FENCE_RE, _OPEN_FENCE_RE
from .base import DegradedSuite, InputPool, Observation, SDLScope, SuiteResult, Task
from .forkserver import run_scenarios
from .gate import VALID, VALID_BEHAVIOURAL, VALID_EXCEPTION_ORACLE, GatedTest
from .observe import nondeterminism_mask, traces_agree
from .oracle_units import (EXCEPTION_UNIT, OracleUnit, find_oracle_units, n_removed,
                           removal_order, weaken_asserts)
from .outcomes import TIMEOUT as OUTCOME_TIMEOUT
from .outcomes import classify_run, static_test_info
from .scenarios import build_pool, extract_scenarios
from .scoring import score_completion

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CORPUS_PATH = _REPO_ROOT / "data" / "realclasseval" / "realclasseval_v1.jsonl.gz"
DEFAULT_MANIFEST_PATH = _REPO_ROOT / "data" / "realclasseval" / "manifest_v1.json"
SPLITS = ("csn", "post_cut-off")
_SPLIT_SHORT = {"csn": "csn", "post_cut-off": "post"}

logger = logging.getLogger(__name__)

# Mirror rq4.consistency's values (see consistency_suite's docstring for why
# they are duplicated, not imported).
_DEFAULT_DIVERGENCE_THRESHOLD = 0.1
_MIN_REFERENCE_SOLUTIONS = 3

# The paper's own user prompt (arXiv 2510.26130, verbatim), so Tier 2 numbers
# stay comparable with the published protocol. The system prompt only adds the
# output-format constraint the extractor relies on.
USER_TEMPLATE = (
    "Implement the following class. Do not explain the code. "
    "The given class skeleton is as follows:\n{skeleton}"
)
SYSTEM_PROMPT = (
    "You are a Python programming assistant. Implement the class exactly as "
    "specified. Return the complete class implementation, including any imports "
    "it needs, as Python code. Do not explain the code."
)

# RQ1: LLM-generated semantic mutants. The class-level analogue of
# rq1.llm_mutator._SYSTEM_PROMPT -- same contract, reworded for "a class" /
# "exactly one method" instead of "a function". FAULT_HINTS (llm_mutator.py)
# is shared as-is across both benchmarks; its hints (loop bounds, guards,
# accumulator updates) apply inside a method body the same way they apply
# inside a function body. Class-specific hints (attribute/state handling) are
# plan-listed future work, not implemented here.
_LLM_MUTATION_SYSTEM_PROMPT = (
    "You are a Python mutation testing expert. "
    "Given a correct Python class, introduce exactly ONE subtle semantic fault "
    "into exactly one method. "
    "The fault must be realistic (a mistake a developer might make), keep the code "
    "syntactically valid, and NOT be a trivial operator swap. "
    "The class you return MUST differ from the one you were given: returning it "
    "unchanged is a failed answer. "
    "Return the complete modified class, including every method -- no explanation, "
    "no markdown fences."
)


# RQ3 SBC reverse generation: rq3.sbc_scorer._REVERSE_GEN_SYSTEM reworded for a
# class, as _LLM_MUTATION_SYSTEM_PROMPT rewords RQ1's.
_SBC_SYSTEM_PROMPT = (
    "You are a software specification analyst. "
    "Given a Python class implementation, infer and describe its intended specification "
    "in 2-4 clear sentences. Describe what the class and its methods are supposed to do, "
    "including edge cases they handle. Do not reference implementation details."
)


class ManifestMissing(RuntimeError):
    """Scoring and task loading need the M0 gate's manifest."""


# ---------------------------------------------------------------------------
# Corpus / manifest I/O
# ---------------------------------------------------------------------------

def load_corpus_rows(path: Path = DEFAULT_CORPUS_PATH) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    rows.sort(key=lambda r: (SPLITS.index(r["split"]), r["snippet_num"]))
    return rows


def task_label_for(row: dict) -> str:
    return f"RCE_{_SPLIT_SHORT[row['split']]}_{row['snippet_id']}"


def _row_to_task(row: dict, task_index: int, docstring_variant: str, meta: dict) -> Task:
    return Task(
        task_id=row["task_id"],
        task_index=task_index,
        label=task_label_for(row),
        split=row["split"],
        prompt=row[f"skeleton_{docstring_variant}"] or "",
        reference_code=row["reference_code"],
        test_code=row["test_code"],
        target=row["class_short_name"],
        module_name=row["snippet_id"],
        meta=meta,
        raw=row,
    )


# ---------------------------------------------------------------------------
# Completion -> executable class module (D7)
# ---------------------------------------------------------------------------

@dataclass
class BuildReport:
    extraction: str                     # fenced | raw | trimmed | failed
    imports_prompt: list[str] = field(default_factory=list)
    imports_completion: list[str] = field(default_factory=list)
    imports_reattached: list[str] = field(default_factory=list)


def _parse(src: str) -> Optional[ast.Module]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        try:
            return ast.parse(src)
        except (SyntaxError, ValueError):
            return None


def _defines_class(tree: Optional[ast.Module], name: str) -> bool:
    return tree is not None and any(isinstance(n, ast.ClassDef) and n.name == name for n in tree.body)


def _top_level_imports(src: str) -> list[str]:
    tree = _parse(src)
    if tree is None:
        return []
    return [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]


def _candidate_sources(raw: str, class_name: str) -> list[tuple[str, str]]:
    """Code regions to try, most specific first: fenced blocks that define the
    class, then any fenced block, then an unclosed fence, then the raw text."""
    fenced = [m.group(1) for m in _FENCE_RE.finditer(raw)]
    defining = [b for b in fenced if re.search(rf"^class\s+{re.escape(class_name)}\b", b, re.M)]
    out = [("fenced", b) for b in defining] + [("fenced", b) for b in fenced if b not in defining]
    open_fence = _OPEN_FENCE_RE.search(raw)
    if not fenced and open_fence:
        out.append(("fenced", raw[open_fence.end():]))
    out.append(("raw", raw))
    return out


def extract_class_module(raw: str, class_name: str) -> tuple[str, str]:
    """Return ``(code, how)``: the completion trimmed to a module that parses
    and defines ``class <class_name>`` at top level.

    Mirrors Tier 1's ``_extract_function_body``: whole modules are kept whole
    (imports and helpers above the class stay), and only unparseable prose
    before or after the code is trimmed. If nothing defines the class, the
    best-effort text is returned unchanged with ``how="failed"``;
    :func:`build_solution_with_report` then runs :func:`no_class_module`
    instead, so the completion scores 0 -- the model's failure, not a harness
    choice.
    """
    for how, src in _candidate_sources(raw, class_name):
        if _defines_class(_parse(src), class_name):
            return src, how
        lines = src.splitlines()
        class_idx = next((i for i, ln in enumerate(lines)
                          if re.match(rf"class\s+{re.escape(class_name)}\b", ln)), None)
        if class_idx is None:
            continue
        # Linear, not quadratic, in the number of lines: first drop leading
        # prose (keeping as much prefix -- imports, helpers -- as still parses),
        # then drop trailing prose with the start at the top or at the class.
        attempts = [(start, len(lines)) for start in range(class_idx + 1)]
        attempts += [(start, end) for end in range(len(lines) - 1, class_idx, -1)
                     for start in dict.fromkeys((0, class_idx))]
        for start, end in attempts:
            candidate = "\n".join(lines[start:end])
            if _defines_class(_parse(candidate), class_name):
                return candidate, "trimmed"
    return _candidate_sources(raw, class_name)[0][1], "failed"


def no_class_module(class_name: str) -> str:
    """The module run for a completion that defines no ``class <class_name>``.

    It fails on import, so every test errors and the completion scores 0 on every
    metric. Running the completion's own text instead (an empty string, prose,
    some other class) makes ``module_0.<class_name>`` raise AttributeError, which
    an exception-oracle test whose reference also raises AttributeError counts as
    a pass: in the S8 run 18 completions without the class scored up to 1.0 that
    way (csn_snippet_156 gives an empty module 1.0). The plan fixed the rule
    before any results: no extractable class, tests fail, score 0.
    """
    return f"raise ImportError({f'completion defines no class {class_name}'!r})\n"


def build_solution_with_report(completion: str, prompt: str, class_name: str) -> tuple[str, BuildReport]:
    code, how = extract_class_module(completion, class_name)
    imports_prompt = _top_level_imports(prompt)
    imports_completion = _top_level_imports(code)
    if how == "failed":
        return no_class_module(class_name), BuildReport(how, imports_prompt, imports_completion, [])
    reattached = [imp for imp in imports_prompt if imp not in imports_completion]
    if reattached:
        code = "\n".join(reattached) + "\n" + code
    return code, BuildReport(how, imports_prompt, imports_completion, reattached)


# ---------------------------------------------------------------------------
# The adapter
# ---------------------------------------------------------------------------

class RealClassEvalBenchmark:
    name = "realclasseval"
    # RQ2 evaluate warms the task's imports up with one reference run and re-runs a
    # completion alone when every test timed out (rq2.evaluator._warm_up and
    # _rerun_whole_suite_timeouts): class suites import torch/sklearn/spacy, and
    # cold parallel imports passed the 30 s timeout in the S8 run. Tier 1 keeps
    # its evaluation unchanged.
    rerun_whole_suite_timeouts = True
    # RQ4 degrades oracle units (asserts, exception tests), not whole tests: the
    # suites average 3.24 valid tests, so whole-test removal empties 307 of 375 at
    # level 0.8. rq4/tier2.py; whole-test degrade() is the sensitivity analysis.
    rq4_design = "oracle_units"

    def __init__(
        self,
        cfg=None,
        corpus_path: Optional[Path] = None,
        manifest_path: Optional[Path] = None,
        splits: Optional[list[str]] = None,
        docstring_variant: str = "full_docstr",
    ) -> None:
        bcfg = getattr(cfg, "benchmark", None)
        self.corpus_path = Path(corpus_path or getattr(bcfg, "data_path", None) or DEFAULT_CORPUS_PATH)
        self.manifest_path = Path(manifest_path or getattr(bcfg, "manifest_path", None) or DEFAULT_MANIFEST_PATH)
        self.splits = list(splits or getattr(bcfg, "splits", None) or SPLITS)
        self.docstring_variant = getattr(bcfg, "docstring_variant", None) or docstring_variant
        self.cfg = cfg
        self._manifest: Optional[dict] = None

    # --- data -----------------------------------------------------------------

    def manifest(self) -> dict:
        if self._manifest is None:
            if not self.manifest_path.exists():
                raise ManifestMissing(
                    f"{self.manifest_path} not found. Run the M0 gate first:\n"
                    "       python scripts/validate_realclasseval.py --config <tier2 config>"
                )
            self._manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return self._manifest

    def corpus_tasks(self) -> list[Task]:
        """Every staged task, ungated, indexed by corpus order. For the gate."""
        rows = [r for r in load_corpus_rows(self.corpus_path) if r["split"] in self.splits]
        return [_row_to_task(r, i, self.docstring_variant, {}) for i, r in enumerate(rows)]

    # --- TaskSource -------------------------------------------------------------

    def load_tasks(self, indices: Optional[list[int]] = None) -> list[Task]:
        accepted = [t for t in self.manifest()["tasks"]
                    if t["status"] == "accepted" and t["split"] in self.splits]
        rows = {r["task_id"]: r for r in load_corpus_rows(self.corpus_path)}
        tasks = [_row_to_task(rows[e["task_id"]], e["task_index"], self.docstring_variant, e)
                 for e in sorted(accepted, key=lambda e: e["task_index"])]
        if indices is None:
            return tasks
        wanted = set(indices)
        missing = sorted(wanted - {t.task_index for t in tasks})
        if missing:
            raise ValueError(f"RealClassEval task index/indices {missing} are not in the "
                             f"manifest (valid range 0..{len(tasks) - 1}).")
        return [t for t in tasks if t.task_index in wanted]

    def generation_messages(self, task: Task, prompt_variant: str) -> list[dict]:
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(skeleton=prompt_variant)},
        ]

    # --- Executor ---------------------------------------------------------------

    def build_solution(self, task: Task, completion: str) -> str:
        return build_solution_with_report(completion, task.prompt, task.target)[0]

    def _gated(self, task: Task) -> list[GatedTest]:
        tests = task.meta.get("tests")
        if tests is None:
            raise ManifestMissing(f"{task.task_id}: no gate verdicts; load tasks via load_tasks()")
        return [GatedTest(name, v["validity"], v.get("ref_exc_type"), v.get("trivial", False))
                for name, v in tests.items() if v["validity"] in VALID]

    def run_suite(self, task, code, timeout_s, suite=None) -> SuiteResult:
        gated = self._gated(task)
        names = [g.nodeid for g in gated]
        extra_valid = suite.extra_valid if suite is not None else None
        if extra_valid:
            # Names RQ4's consistency assertions add: outside the M0 gate's own
            # valid-test list (they did not exist when the gate ran), so they
            # are unioned in here rather than being filtered out as unknown.
            names = names + [n for n in extra_valid if n not in names]
        subset = suite.subset if suite is not None else None
        if subset is not None:
            names = [n for n in names if n in subset]
        test_code = suite.test_code if suite is not None and suite.test_code is not None else task.test_code
        if not names:
            # A degraded suite with every test removed (RQ4 at 0.8 on a task of up
            # to 4 valid tests). execute_pytest with no selection would run the
            # whole file; the scope is empty, so the score is None either way.
            return SuiteResult(outcomes={}, scores=self.score_outcomes(task, {}, subset, extra_valid))
        run = execute_pytest(task.module_name, code, test_code, timeout_s=timeout_s, select=names)
        outcomes = classify_run(
            run, static_test_info(test_code),
            ref_exc_types={g.nodeid: g.ref_exc_type for g in gated if g.ref_exc_type},
            requested=names,
        )
        return SuiteResult(outcomes=outcomes, scores=self.score_outcomes(task, outcomes, subset, extra_valid))

    def score_outcomes(self, task, outcomes, subset=None, extra_valid=None) -> dict[str, Optional[float]]:
        """D3 scores from stored outcomes; ``subset`` restricts to those tests
        (RQ4 reuse). An empty scope has no score, not a zero.

        ``extra_valid`` names tests outside the M0 gate (RQ4's consistency
        assertions) that should count as valid_behavioural for this call only
        -- synthetic GatedTest entries, not a change to the task's own gate
        record. Only names actually present in ``outcomes`` are added, so a
        caller passing names that were never run does not silently inflate
        the valid-test count.
        """
        gated = list(self._gated(task))
        if extra_valid:
            known = {g.nodeid for g in gated}
            gated += [GatedTest(n, VALID_BEHAVIOURAL) for n in extra_valid
                     if n in outcomes and n not in known]
        gated = [g for g in gated if subset is None or g.nodeid in subset]
        if not gated:
            return {"primary": None, "passed_all": None, "behavioural_pass_rate": None,
                    "nontrivial_pass_rate": None, "pytest_native_pass_rate": None, "n_valid": 0}
        s = score_completion(gated, outcomes)
        return {
            "primary": s.pass_rate,
            "passed_all": 1.0 if s.passed_all else 0.0,
            "behavioural_pass_rate": s.behavioural_pass_rate,
            "nontrivial_pass_rate": s.nontrivial_pass_rate,
            "pytest_native_pass_rate": s.pytest_native_pass_rate,
            "n_valid": s.n_valid,
        }

    def suite_timed_out(self, result: SuiteResult) -> bool:
        return any(o.outcome == OUTCOME_TIMEOUT for o in result.outcomes.values())

    def sbc_spec(self, task: Task) -> dict:
        """RQ3's SBC request for a class: class wording, and every docstring of the
        skeleton as the reference (the class docstring alone, which the Tier 1
        regex finds, leaves out the methods' specifications; median 4 per task)."""
        import inspect

        from ..rq2.corpus import docstring_texts
        try:
            docs = [inspect.cleandoc(d) for d in docstring_texts(task.prompt)]
        except (SyntaxError, ValueError):
            docs = []
        return {
            "system": _SBC_SYSTEM_PROMPT,
            "user_label": "Class implementation",
            "reference": "\n\n".join(d for d in docs if d.strip()),
        }

    # --- ScenarioProvider -------------------------------------------------------

    def input_pool(self, task: Task, n: int, seed: int) -> InputPool:
        header, scenarios = extract_scenarios(task.test_code, task.module_name)
        excluded = set(task.meta.get("scenarios", {}).get("excluded", {}))
        originals = [s for s in scenarios if s.scenario_id not in excluded]
        pool = build_pool(header, originals, n, seed)
        return InputPool(items=pool.scenarios, header=header, composition=pool.composition())

    def observe(self, task, code, pool, timeout_s) -> list[Observation]:
        return run_scenarios(task.module_name, code, pool.header, pool.items, timeout_s=timeout_s)

    def observe_one(self, task, code, pool, index, timeout_s) -> Observation:
        return run_scenarios(task.module_name, code, pool.header, [pool.items[index]], timeout_s=timeout_s)[0]

    def reference_observations(self, task, pool, timeout_s):
        """Run the reference twice: the first run is the observation, the
        difference between runs is the nondeterminism mask (D5). An item the
        reference does not complete identically-statused in both runs is
        returned with the non-ok status, so callers skip it."""
        run1 = self.observe(task, task.reference_code, pool, timeout_s)
        run2 = self.observe(task, task.reference_code, pool, timeout_s)
        obs, masks = [], []
        for a, b in zip(run1, run2):
            if a["status"] == "ok" and b["status"] == "ok":
                obs.append(a)
                masks.append(frozenset(nondeterminism_mask(a["tokens"], b["tokens"])))
            else:
                obs.append(a if a["status"] != "ok" else b)
                masks.append(frozenset())
        return obs, masks

    def observations_agree(self, a, b, mask=frozenset()) -> bool:
        if "timeout" in (a["status"], b["status"]) or a["status"] != b["status"]:
            return False
        return traces_agree(a["tokens"], b["tokens"], mask)

    def is_timeout(self, obs) -> bool:
        return obs["status"] == "timeout"

    def is_error(self, obs) -> bool:
        return obs["status"] in ("crashed", "import_error")

    # --- MutationScope ----------------------------------------------------------

    def mutation_source(self, task: Task) -> str:
        return task.reference_code

    def sdl_scope(self, task: Task) -> Optional[SDLScope]:
        class_name = task.target

        def methods(tree: ast.Module) -> list:
            for node in tree.body:
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    return [n for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
            return []

        return methods

    def llm_mutation_messages(self, task: Task, fault_hint: str) -> list[dict]:
        hint = f"\n\n{fault_hint}" if fault_hint else ""
        user = f"Introduce one subtle semantic fault into this class:\n\n{task.reference_code}{hint}"
        return [
            {"role": "system", "content": _LLM_MUTATION_SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

    def repair_mutant(self, task: Task, code: str) -> Optional[str]:
        """Make an LLM-returned mutant class runnable, or None if it cannot be.

        Reuses the D7 extractor (:func:`extract_class_module`), then
        re-attaches the REFERENCE's own imports if the mutant dropped any --
        not the prompt's (the model was shown the full reference class here,
        not a bare skeleton, so the reference's imports are what it actually
        saw; this is the RQ1 analogue of D7's completion policy, not D7
        itself).
        """
        extracted, how = extract_class_module(code, task.target)
        if how == "failed":
            return None
        missing = [i for i in _top_level_imports(task.reference_code) if i not in _top_level_imports(extracted)]
        if missing:
            extracted = "\n".join(missing) + "\n" + extracted
        return extracted

    # --- SuiteDegrader ----------------------------------------------------------

    def degrade(self, task: Task, level: float, seed: int) -> DegradedSuite:
        """Remove ``ceil(level * n)`` whole valid tests. One seeded shuffle,
        then prefixes, so the levels are nested (the 0.5 suite lacks
        everything the 0.2 suite lacks) -- as Tier 1's assert degradation."""
        names = [g.nodeid for g in self._gated(task)]
        order = list(range(len(names)))
        random.Random(seed).shuffle(order)
        n_remove = min(math.ceil(len(names) * level), len(names)) if level > 0 else 0
        removed = {names[i] for i in order[:n_remove]}
        return DegradedSuite(level=level, subset=frozenset(n for n in names if n not in removed))

    def oracle_units(self, task: Task) -> list[OracleUnit]:
        """RQ4's oracle units for this task (plan rev. 6, 8.1; see oracle_units.py)."""
        tests = task.meta.get("tests") or {}
        return find_oracle_units(task.test_code, task.module_name,
                                 [n for n, v in tests.items() if v["validity"] == VALID_BEHAVIOURAL],
                                 [n for n, v in tests.items() if v["validity"] == VALID_EXCEPTION_ORACLE])

    def degrade_units(self, task: Task, level: float, seed: int) -> tuple[DegradedSuite, dict]:
        """RQ4's primary degradation: remove ``ceil(level * n)`` oracle units.

        Assert units are weakened in place (``test_code``), exception units leave
        the selected suite (``subset``). One seeded shuffle per task, then
        prefixes, so the levels are nested. Level 0 (nothing removed) is the plain
        intact suite, the exact call RQ2's evaluator makes. ``info`` records the
        counts and the removed unit ids; ``n_remaining == 0`` is a missing level.
        """
        tests = task.meta.get("tests") or {}
        behavioural = [n for n, v in tests.items() if v["validity"] == VALID_BEHAVIOURAL]
        exception = [n for n, v in tests.items() if v["validity"] == VALID_EXCEPTION_ORACLE]
        units = find_oracle_units(task.test_code, task.module_name, behavioural, exception)
        k = n_removed(len(units), level)
        removed = removal_order(units, f"{seed}|{task.task_id}")[:k]
        info = {"n_units": len(units), "n_removed": k, "n_remaining": len(units) - k,
                "removed": removed}
        if not removed:
            return DegradedSuite(level=level), info
        kind = {u.unit_id: u for u in units}
        dropped_tests = {kind[i].test for i in removed if kind[i].kind == EXCEPTION_UNIT}
        test_code = weaken_asserts(task.test_code, task.module_name, behavioural, exception, removed)
        subset = (frozenset(g.nodeid for g in self._gated(task) if g.nodeid not in dropped_tests)
                  if dropped_tests else None)
        return DegradedSuite(level=level, subset=subset,
                             test_code=None if test_code == task.test_code else test_code), info

    def consistency_suite(self, task: Task, divergence_data: dict, threshold, max_assertions: int = 20):
        """Build ``test_ca_<i>`` functions from RQ3's generic consensus.

        Each function replays one scenario via
        ``forkserver._run_scenario`` (reused, not re-derived: it is the same
        code the original observation was produced by) and asserts the
        resulting trace matches the recorded majority-vote tokens, excluding
        any key this task's nondeterminism mask covers.

        Same threshold/MIN_REFERENCE_SOLUTIONS gating as Tier 1's
        ``build_consistency_assertions`` (values duplicated here rather than
        imported from ``rq4.consistency`` -- that module already imports
        from ``benchmarks``, so the reverse import would cycle).
        """
        rate = divergence_data.get("pairwise_disagreement_rate")
        effective_threshold = threshold if threshold is not None else _DEFAULT_DIVERGENCE_THRESHOLD
        if rate is None or rate < effective_threshold:
            return "", 0
        if divergence_data.get("n_solutions", 0) < _MIN_REFERENCE_SOLUTIONS:
            return "", 0

        entries = [e for e in divergence_data.get("consensus", {}).get("entries", [])
                  if "scenario_index" in e][:max_assertions]
        n_shared = divergence_data.get("n_shared_inputs_requested")
        seed = divergence_data.get("seed")
        if not entries or n_shared is None or seed is None:
            return "", 0

        pool = self.input_pool(task, n_shared, seed)
        masks = task.meta.get("scenarios", {}).get("masks", {})

        blocks: list[str] = []
        for e in entries:
            idx = e["scenario_index"]
            if idx >= len(pool.items):
                continue
            scenario = pool.items[idx]
            expected_obs = e.get("expected_obs")
            if not isinstance(expected_obs, dict) or expected_obs.get("status") != "ok":
                continue  # defensive: voting already excludes non-"ok" observations
            masked = set(masks.get(scenario.scenario_id, []))
            expected_tokens = {k: v for k, v in expected_obs.get("tokens", {}).items() if k not in masked}
            if not expected_tokens:
                continue
            i = len(blocks)
            steps = [asdict(s) for s in scenario.steps]
            # repr() the WHOLE message as one Python literal, rather than
            # hand-assembling quoted text with scenario_id's own !r spliced
            # into it: that collides whenever scenario_id's repr uses the same
            # quote character as the surrounding literal (e.g. a scenario_id
            # containing a plain word still reprs with single quotes, which
            # then prematurely closes a single-quoted template string).
            message = f"Consistency violation on scenario {scenario.scenario_id!r}: %r"
            blocks.append(
                f"def test_ca_{i}():\n"
                f"    from meta_real_eval.benchmarks.forkserver import _run_scenario\n"
                f"    _ca_steps = {steps!r}\n"
                f"    _ca_trace = _run_scenario(_ca_steps, dict(globals()))\n"
                f"    _ca_expected = {expected_tokens!r}\n"
                f"    _ca_mismatches = {{k: (_ca_trace.get(k), v) for k, v in _ca_expected.items() "
                f"if _ca_trace.get(k) != v}}\n"
                f"    assert not _ca_mismatches, {message!r} % _ca_mismatches\n"
            )

        if not blocks:
            return "", 0

        code = (
            f"# Consistency assertions for {task.task_id} (unanimous-consensus pseudo-oracle)\n"
            f"# Divergence rate {rate:.3f} >= threshold {effective_threshold}; "
            f"{len(blocks)} consensus scenario(s)\n\n" + "\n\n".join(blocks)
        )
        try:
            compile(code, "<consistency_assertions>", "exec")
        except SyntaxError:
            logger.warning("Generated class-level assertions for %s do not compile - skipping",
                           task.task_id)
            return "", 0
        return code, len(blocks)

    def augmented_suite(self, task: Task, degraded: DegradedSuite, ca_code: str, ca_count: int) -> DegradedSuite:
        if not ca_code:
            return degraded
        ca_names = frozenset(f"test_ca_{i}" for i in range(ca_count))
        # On top of the degraded source: under oracle-unit degradation its asserts
        # are weakened in test_code (whole-test degradation leaves it None).
        base = degraded.test_code if degraded.test_code is not None else task.test_code
        test_code = base + "\n\n" + ca_code
        subset = (degraded.subset | ca_names) if degraded.subset is not None else None
        return DegradedSuite(level=degraded.level, subset=subset, test_code=test_code, extra_valid=ca_names)
