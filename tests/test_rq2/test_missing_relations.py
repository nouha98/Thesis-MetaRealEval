"""compute_ranking_stability under an absent relation, and the coverage split.

Two regressions, both about the difference between "measured, no effect" and
"never measured":

1. A corpus variant the generator could not fill leaves its relation with no
   cell at all.  `delta_pass_at_1` used to read that absent relation through
   ``.get(model_id, 0.0)``, producing ``delta = 0 - baseline`` -- a fabricated
   collapse to zero that then became the model's largest observed sensitivity --
   and `rank_change` used to rank the empty score dict, whose all-zero vector
   ties every model at the mid rank and so invented a movement of up to one
   place.  At the pilot's ~22% unfilled slot rate those artefacts would have
   dominated the per-model figures.

2. Generation coverage was counted from the *tau_b* values.  A family is
   generated but tau-undefined exactly when all models tie under it, so the
   coverage gate excluded tasks for being STABLE -- selection on the dependent
   variable.  The two counts are now separate keys.
"""

import json

import pytest

from meta_real_eval.core.checkpoint import task_dir
from meta_real_eval.core.config import Config
from meta_real_eval.core.data_loader import HumanEvalTask
from meta_real_eval.rq2.ranking import compute_ranking_stability

MODELS = ["m_a", "m_b", "m_c"]


@pytest.fixture
def cfg(tmp_path):
    return Config.model_validate({
        "project": {"output_dir": str(tmp_path), "mock": True},
        "llm": {"models": [{"id": m} for m in MODELS]},
        "rq2": {"template_relations": ["formal"], "include_control_resample": False},
    })


@pytest.fixture
def task():
    return HumanEvalTask(
        task_id="HumanEval/0", task_index=0, prompt="def f():\n    pass\n",
        entry_point="f", test="", canonical_solution="",
    )


def _rates(scores: dict[str, float]) -> dict:
    return {m: {"pass@1": s, "n": 10} for m, s in scores.items()}


def _run(cfg, task, pass_rates: dict) -> dict:
    out = task_dir(cfg, "rq2", "HumanEval_0", phase="evaluate")
    out.mkdir(parents=True, exist_ok=True)
    (out / "pass_rates.json").write_text(json.dumps(pass_rates))
    compute_ranking_stability(task, cfg)
    return json.loads((out / "rankings.json").read_text())


# ---------------------------------------------------------------------------
# 1. An absent relation is missing data, not a score of zero
# ---------------------------------------------------------------------------

def test_an_absent_relation_yields_no_delta_and_no_rank_change(cfg, task):
    # `formal` is a configured relation with no cell at all -- the shape a
    # corpus generation gap takes downstream.
    r = _run(cfg, task, {"original": _rates({"m_a": 0.9, "m_b": 0.5, "m_c": 0.2})})

    assert r["delta_pass_at_1"]["m_a"]["formal"] is None      # not -0.9
    assert r["rank_change"]["m_a"]["formal"] is None          # not -1.0
    assert r["tau_b_per_relation"]["formal"] is None
    assert r["incomplete_relations"] == ["formal"]


def test_a_model_with_no_defined_delta_anywhere_summarises_as_none(cfg, task):
    """0.0 would read as 'paraphrase never moved this model'."""
    r = _run(cfg, task, {"original": _rates({"m_a": 0.9, "m_b": 0.5, "m_c": 0.2})})

    assert r["mean_abs_delta_pass_at_1"]["m_a"] is None
    assert r["mean_abs_rank_change"]["m_a"] is None


def test_a_present_relation_still_produces_real_numbers(cfg, task):
    r = _run(cfg, task, {
        "original": _rates({"m_a": 0.9, "m_b": 0.5, "m_c": 0.2}),
        "formal": _rates({"m_a": 0.5, "m_b": 0.9, "m_c": 0.2}),
    })

    assert r["delta_pass_at_1"]["m_a"]["formal"] == pytest.approx(-0.4)
    assert r["rank_change"]["m_a"]["formal"] == pytest.approx(-1.0)   # rank 1 -> 2
    assert r["mean_abs_delta_pass_at_1"]["m_a"] == pytest.approx(0.4)


def test_an_empty_model_cell_is_treated_as_missing_not_as_zero(cfg, task):
    """n=0 is an infrastructure failure, not a model that answered wrongly."""
    r = _run(cfg, task, {
        "original": _rates({"m_a": 0.9, "m_b": 0.5, "m_c": 0.2}),
        "formal": {"m_a": {"pass@1": 0.5, "n": 10}, "m_b": {"pass@1": 0.9, "n": 10},
                   "m_c": {"pass@1": 0.0, "n": 0}},
    })

    assert r["incomplete_relations"] == ["formal"]
    assert r["delta_pass_at_1"]["m_a"]["formal"] is None


# ---------------------------------------------------------------------------
# 2. Generation coverage vs. tau_b definedness
# ---------------------------------------------------------------------------

def _llm_cfg(tmp_path):
    cfg = Config.model_validate({
        "project": {"output_dir": str(tmp_path), "mock": True},
        "llm": {"models": [{"id": m} for m in MODELS]},
        "rq2": {"template_relations": [], "include_control_resample": False},
    })
    # `cfg.rq2.relations` derives the LLM variant ids from the corpus FILE, which
    # a unit test has no reason to build. relation_arm() classifies by key shape
    # alone, so seeding the same ids here produces the identical relation list a
    # real corpus run would, without the I/O.
    cfg.rq2.template_relations = [
        f"llm_{fam}_01"
        for fam in ("lexical", "reorder", "formal", "persona", "terse")
    ]
    return cfg


def test_a_generated_family_counts_as_covered_even_when_all_models_tie(tmp_path, task):
    """The bug: a task where the leaderboard cannot move was reported as a task
    short of paraphrases, so the coverage gate dropped it for being STABLE."""
    cfg = _llm_cfg(tmp_path)
    tied = _rates({"m_a": 1.0, "m_b": 1.0, "m_c": 1.0})
    pass_rates = {"original": _rates({"m_a": 0.9, "m_b": 0.5, "m_c": 0.2})}
    for fam in ("lexical", "reorder", "formal", "persona", "terse"):
        pass_rates[f"llm_{fam}_01"] = tied

    r = _run(cfg, task, pass_rates)

    assert r["n_families_generated"] == 5              # all five were generated
    assert r["n_families_with_defined_tau"] == 0       # none could move the ranking
    assert r["degenerate_relations"] == [f"llm_{f}_01" for f in
                                         ("lexical", "reorder", "formal",
                                          "persona", "terse")]
    assert r["incomplete_relations"] == []


def test_an_ungenerated_family_does_not_count_as_covered(tmp_path, task):
    cfg = _llm_cfg(tmp_path)
    pass_rates = {"original": _rates({"m_a": 0.9, "m_b": 0.5, "m_c": 0.2})}
    for fam in ("lexical", "reorder", "formal"):
        pass_rates[f"llm_{fam}_01"] = _rates({"m_a": 0.5, "m_b": 0.9, "m_c": 0.2})

    r = _run(cfg, task, pass_rates)

    assert r["families_generated"] == ["formal", "lexical", "reorder"]
    assert r["n_families_generated"] == 3
    assert sorted(r["incomplete_relations"]) == ["llm_persona_01", "llm_terse_01"]
    assert r["degenerate_relations"] == []
