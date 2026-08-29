"""scripts/analyze_results.py: paired understatement and the coverage gate.

Regression tests for a real bug: `_understatement` used to receive two lists
(`per_arm_tau["template"]`, `per_arm_tau["llm"]`) built independently -- a task
missing one arm still contributed to the other, so the two means it differenced
were computed over two different, uncontrolled task samples, while the
function's own docstring claimed "paired per task". The tell was that it
reported `n_tasks_template` and `n_tasks_llm` as two different numbers.

``scripts/analyze_results.py`` is a script, not a package module, so it is
loaded the same way ``scripts/generate_paraphrases.py`` is: by file path.
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))


def _load_analyze_results():
    spec = importlib.util.spec_from_file_location(
        "analyze_results_under_test", REPO_ROOT / "scripts" / "analyze_results.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ar(tmp_path):
    module = _load_analyze_results()
    module.RESULTS = tmp_path
    return module


def _write_rankings(results_dir: Path, task: str, tau_b_per_relation: dict) -> None:
    d = results_dir / "rq2" / "evaluate" / task
    d.mkdir(parents=True, exist_ok=True)
    (d / "rankings.json").write_text(json.dumps({
        "model_ids": ["m1", "m2", "m3"],
        "tau_b_per_relation": tau_b_per_relation,
        "delta_pass_at_1": {}, "rank_change": {},
        "mean_abs_delta_pass_at_1": {}, "mean_abs_rank_change": {},
    }))


FULL_TEMPLATE = {"control_resample": 0.9, "persona": 1.0, "formal": 1.0,
                 "reorder": 1.0, "terse": 1.0}


def _full_llm(value: float) -> dict:
    return {f"llm_{fam}_0{j}": value
            for fam in ("lexical", "reorder", "formal", "persona", "terse")
            for j in (1, 2, 3)}


def _thin_llm(value: float, family: str = "lexical") -> dict:
    return {f"llm_{family}_0{j}": value for j in (1, 2, 3)}


# ---------------------------------------------------------------------------
# The pairing bug
# ---------------------------------------------------------------------------

def test_a_task_without_an_llm_arm_does_not_pollute_the_paired_statistic(ar, tmp_path):
    # Ten tasks with both arms (template=1.0, llm=0.2); five tasks with a
    # template arm but NO llm arm at all. The unpaired five must not leak into
    # either mean of the paired comparison.
    for i in range(10):
        _write_rankings(tmp_path, f"HumanEval_{i}", {**FULL_TEMPLATE, **_full_llm(0.2)})
    for i in range(10, 15):
        _write_rankings(tmp_path, f"HumanEval_{i}", dict(FULL_TEMPLATE))

    rs = ar.analyze_rq2()["ranking_stability"]
    u = rs["template_understatement"]
    assert u["n_tasks_paired"] == 10
    assert u["template_mean_tau_b"] == pytest.approx(1.0)
    assert u["llm_mean_tau_b"] == pytest.approx(0.2)


def test_thin_coverage_tasks_are_excluded_from_the_paired_statistic(ar, tmp_path):
    # Ten well-covered tasks (llm=0.2); five tasks with only 1/5 families
    # filled, and deliberately given a DIFFERENT llm value (1.0) so any leak
    # into the paired mean is visible rather than accidentally cancelling out.
    for i in range(10):
        _write_rankings(tmp_path, f"HumanEval_{i}", {**FULL_TEMPLATE, **_full_llm(0.2)})
    for i in range(10, 15):
        _write_rankings(tmp_path, f"HumanEval_{i}", {**FULL_TEMPLATE, **_thin_llm(1.0)})

    rs = ar.analyze_rq2()["ranking_stability"]
    u = rs["template_understatement"]
    assert u["n_tasks_paired"] == 10
    assert u["llm_mean_tau_b"] == pytest.approx(0.2)   # not polluted toward 1.0


# ---------------------------------------------------------------------------
# Coverage gate
# ---------------------------------------------------------------------------

def test_thin_coverage_task_is_excluded_from_the_primary_mean_and_listed(ar, tmp_path):
    _write_rankings(tmp_path, "HumanEval_0", {**FULL_TEMPLATE, **_full_llm(0.2)})
    _write_rankings(tmp_path, "HumanEval_1", {**FULL_TEMPLATE, **_thin_llm(1.0)})

    rs = ar.analyze_rq2()["ranking_stability"]
    assert rs["n_task_level_samples"] == 1
    assert rs["grand_mean_tau_b"] == pytest.approx(0.2)
    assert rs["coverage"]["n_tasks_excluded"] == 1
    excluded = rs["coverage"]["excluded_tasks"][0]
    assert excluded["task"] == "HumanEval_1"
    assert excluded["n_families_covered"] == 1
    assert excluded["families_covered"] == ["lexical"]


def test_a_task_with_exactly_the_minimum_families_is_not_excluded(ar, tmp_path):
    from meta_real_eval.rq2.corpus import MIN_FAMILIES_COVERED, FAMILIES
    families = FAMILIES[:MIN_FAMILIES_COVERED]
    variants = {f"llm_{fam}_01": 0.2 for fam in families}
    _write_rankings(tmp_path, "HumanEval_0", {**FULL_TEMPLATE, **variants})

    rs = ar.analyze_rq2()["ranking_stability"]
    assert rs["coverage"]["n_tasks_excluded"] == 0
    assert rs["n_task_level_samples"] == 1


def test_a_template_only_task_is_exempt_from_the_coverage_gate(ar, tmp_path):
    # No LLM arm at all (corpus not configured for this run) -- there is
    # nothing to under-cover, and mean_tau_b falls back to the template arm.
    _write_rankings(tmp_path, "HumanEval_0", dict(FULL_TEMPLATE))

    rs = ar.analyze_rq2()["ranking_stability"]
    assert rs["coverage"]["n_tasks_excluded"] == 0
    assert rs["n_task_level_samples"] == 1
    assert rs["grand_mean_tau_b"] == pytest.approx(1.0)


def test_per_family_diagnostics_are_not_gated_by_task_level_coverage(ar, tmp_path):
    # A task with only `lexical` filled still contributes a real lexical
    # observation to by_llm_family -- the coverage gate protects the task-level
    # summary, not individual per-family aggregates.
    _write_rankings(tmp_path, "HumanEval_0", {**FULL_TEMPLATE, **_thin_llm(0.5, "lexical")})

    rs = ar.analyze_rq2()["ranking_stability"]
    assert rs["coverage"]["n_tasks_excluded"] == 1        # excluded from the task-level mean
    assert rs["by_llm_family"]["lexical"]["n"] == 1        # but still counted here


# ---------------------------------------------------------------------------
# Complete-case sensitivity check
# ---------------------------------------------------------------------------

def test_complete_case_sensitivity_only_counts_5_of_5_tasks(ar, tmp_path):
    from meta_real_eval.rq2.corpus import MIN_FAMILIES_COVERED, FAMILIES
    # One task with all 5 families (passes both the >=4 gate and the 5/5 check);
    # one task with exactly MIN_FAMILIES_COVERED (passes the gate, fails 5/5,
    # unless MIN_FAMILIES_COVERED == len(FAMILIES)).
    _write_rankings(tmp_path, "HumanEval_0", {**FULL_TEMPLATE, **_full_llm(0.2)})
    partial = {f"llm_{fam}_01": 0.6 for fam in FAMILIES[:MIN_FAMILIES_COVERED]}
    _write_rankings(tmp_path, "HumanEval_1", {**FULL_TEMPLATE, **partial})

    rs = ar.analyze_rq2()["ranking_stability"]
    cc = rs["complete_case_sensitivity"]
    if MIN_FAMILIES_COVERED < len(FAMILIES):
        assert cc["n"] == 1
        assert cc["mean_tau_b"] == pytest.approx(0.2)
    else:
        assert cc["n"] == 2


# ---------------------------------------------------------------------------
# The coverage gate counts GENERATED families, not tau-defined ones
# ---------------------------------------------------------------------------

def _write_rankings_v2(results_dir: Path, task: str, tau_b_per_relation: dict,
                       families_generated: list[str]) -> None:
    """A rankings.json in the current format, which reports the two coverage
    counts separately (see rq2/ranking.py)."""
    d = results_dir / "rq2" / "evaluate" / task
    d.mkdir(parents=True, exist_ok=True)
    (d / "rankings.json").write_text(json.dumps({
        "model_ids": ["m1", "m2", "m3"],
        "tau_b_per_relation": tau_b_per_relation,
        "families_generated": sorted(families_generated),
        "n_families_generated": len(families_generated),
        "delta_pass_at_1": {}, "rank_change": {},
        "mean_abs_delta_pass_at_1": {}, "mean_abs_rank_change": {},
    }))


def test_a_task_whose_families_all_tie_is_not_excluded_as_under_covered(ar, tmp_path):
    """The selection-on-the-dependent-variable bug.

    All five families were generated, but on this task every model ties under
    four of them, so only one family yields a defined tau_b. Counting coverage
    from the tau values called that "1/5 families filled" and dropped the task --
    and a task whose models tie is precisely a task whose ranking did NOT move,
    so the exclusion removed stable tasks and biased the mean tau_b downward.
    """
    _write_rankings_v2(
        tmp_path, "HumanEval_0",
        {**FULL_TEMPLATE,
         **{f"llm_{fam}_01": None for fam in ("lexical", "reorder", "formal", "persona")},
         "llm_terse_01": 1.0},
        families_generated=["lexical", "reorder", "formal", "persona", "terse"],
    )

    rs = ar.analyze_rq2()["ranking_stability"]
    assert rs["coverage"]["n_tasks_excluded"] == 0
    assert rs["n_task_level_samples"] == 1


def test_a_task_genuinely_short_of_generated_families_is_still_excluded(ar, tmp_path):
    _write_rankings_v2(
        tmp_path, "HumanEval_0", {**FULL_TEMPLATE, **_thin_llm(0.2, "lexical")},
        families_generated=["lexical"],
    )

    rs = ar.analyze_rq2()["ranking_stability"]
    assert rs["coverage"]["n_tasks_excluded"] == 1
    assert rs["coverage"]["excluded_tasks"][0]["families_covered"] == ["lexical"]


def test_legacy_rankings_without_the_split_are_counted_not_silently_regated(ar, tmp_path):
    _write_rankings(tmp_path, "HumanEval_0", {**FULL_TEMPLATE, **_thin_llm(0.2)})

    rs = ar.analyze_rq2()["ranking_stability"]
    assert rs["coverage"]["n_tasks_legacy_coverage_fallback"] == 1


def test_a_template_only_run_raises_no_legacy_coverage_warning(ar, tmp_path):
    """It was never gated either way, so there is nothing to re-run."""
    _write_rankings(tmp_path, "HumanEval_0", dict(FULL_TEMPLATE))

    rs = ar.analyze_rq2()["ranking_stability"]
    assert rs["coverage"]["n_tasks_legacy_coverage_fallback"] == 0


# ---------------------------------------------------------------------------
# Coverage-gate sensitivity ladder
# ---------------------------------------------------------------------------

def test_coverage_sensitivity_brackets_the_headline_over_nested_samples(ar, tmp_path):
    # Five tasks with all 5 families (tau 0.2); five with 4/5 (tau 0.2); five
    # with 1/5 and a deliberately different tau, so each rung's sample is
    # visible in its mean.
    from meta_real_eval.rq2.corpus import FAMILIES
    for i in range(5):
        _write_rankings_v2(tmp_path, f"HumanEval_{i}",
                           {**FULL_TEMPLATE, **_full_llm(0.2)}, list(FAMILIES))
    for i in range(5, 10):
        _write_rankings_v2(tmp_path, f"HumanEval_{i}",
                           {**FULL_TEMPLATE,
                            **{f"llm_{f}_01": 0.2 for f in FAMILIES[:4]}},
                           list(FAMILIES[:4]))
    for i in range(10, 15):
        _write_rankings_v2(tmp_path, f"HumanEval_{i}",
                           {**FULL_TEMPLATE, **_thin_llm(1.0, "lexical")},
                           ["lexical"])

    cs = ar.analyze_rq2()["ranking_stability"]["coverage_sensitivity"]
    assert cs["ungated"]["n"] == 15
    assert cs["primary_gate"]["n"] == 10
    assert cs["complete_case"]["n"] == 5
    # The excluded thin tasks pull the ungated mean up; the gated rungs agree.
    assert cs["ungated"]["mean"] == pytest.approx(0.2 * 10 / 15 + 1.0 * 5 / 15)
    assert cs["primary_gate"]["mean"] == pytest.approx(0.2)
    assert cs["complete_case"]["mean"] == pytest.approx(0.2)
