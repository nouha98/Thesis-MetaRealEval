"""RQ3 must not inherit RQ2's full variant count.

Divergence costs O(n_solutions * n_shared_inputs) subprocess spawns. At 20
relations x 3 models x 200 inputs x 164 tasks that is roughly two million, and it
would also invalidate the calibrated ``tau_div``, which was derived at k=15
solutions. RQ3 therefore samples one variant per family, seeded.
"""

from meta_real_eval.core.config import Config
from meta_real_eval.rq3.runner import select_divergence_relations

RELATIONS = [
    "original", "control_resample",
    "persona", "formal", "reorder", "terse",
    "llm_lexical_01", "llm_lexical_02", "llm_lexical_03",
    "llm_reorder_01", "llm_reorder_02", "llm_reorder_03",
    "llm_formal_01", "llm_formal_02", "llm_formal_03",
    "llm_persona_01", "llm_persona_02", "llm_persona_03",
    "llm_terse_01", "llm_terse_02", "llm_terse_03",
]


def cfg(seed=42, per_family=1):
    return Config.model_validate({
        "project": {"seed": seed},
        "rq3": {"variant_sample_per_family": per_family},
    })


def test_samples_one_variant_per_family_plus_the_original():
    selected = select_divergence_relations(cfg(), "HumanEval_0", RELATIONS)
    assert selected[0] == "original"
    assert len(selected) == 6                       # original + 5 families
    families = [r.split("_")[1] for r in selected[1:]]
    assert sorted(families) == ["formal", "lexical", "persona", "reorder", "terse"]


def test_templates_and_the_control_are_excluded():
    selected = select_divergence_relations(cfg(), "HumanEval_0", RELATIONS)
    # Templates are RQ2's control arm and are mostly no-ops on the prompt, so
    # they would contribute near-duplicate solutions; control_resample is the
    # original prompt again, so its divergence would measure sampling noise.
    assert not {"persona", "formal", "reorder", "terse", "control_resample"} & set(selected)


def test_selection_is_deterministic_for_a_task():
    a = select_divergence_relations(cfg(), "HumanEval_7", RELATIONS)
    b = select_divergence_relations(cfg(), "HumanEval_7", RELATIONS)
    assert a == b


def test_different_tasks_do_not_all_pick_the_same_slot():
    # Seeding on the task label as well as project.seed keeps the choice
    # reproducible without pinning every task to variant 01, which would make the
    # corpus's other two variants per family dead weight in RQ3.
    picks = {
        tuple(select_divergence_relations(cfg(), f"HumanEval_{i}", RELATIONS))
        for i in range(30)
    }
    assert len(picks) > 1


def test_changing_the_seed_changes_the_sample():
    a = select_divergence_relations(cfg(seed=1), "HumanEval_0", RELATIONS)
    b = select_divergence_relations(cfg(seed=2), "HumanEval_0", RELATIONS)
    assert a != b


def test_sample_size_is_configurable():
    selected = select_divergence_relations(cfg(per_family=2), "HumanEval_0", RELATIONS)
    assert len(selected) == 11                      # original + 5 families x 2


def test_falls_back_to_every_relation_without_a_corpus():
    # Pre-corpus behaviour: with no LLM variants to sample there is nothing to
    # contain, so RQ3 keeps using the relations it always did.
    legacy = ["original", "control_resample", "persona", "formal", "reorder", "terse"]
    selected = select_divergence_relations(cfg(), "HumanEval_0", legacy)
    assert selected == ["original", "persona", "formal", "reorder", "terse"]
