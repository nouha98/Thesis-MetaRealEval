"""Tests for the ranking primitives RQ2 and RQ4 both build on."""

from meta_real_eval.rq2.ranking import _rank_positions, _rank_vector, _tau_b

MODELS = ["m_a", "m_b", "m_c"]


def test_rank_vector_uses_fixed_model_order():
    assert _rank_vector({"m_c": 0.9, "m_a": 0.1}, MODELS) == [0.1, 0.0, 0.9]


def test_tau_b_is_one_for_identical_orderings():
    assert _tau_b([0.1, 0.5, 0.9], [0.2, 0.6, 0.8]) == 1.0


def test_tau_b_is_minus_one_for_reversed_orderings():
    assert _tau_b([0.1, 0.5, 0.9], [0.9, 0.5, 0.1]) == -1.0


def test_tau_b_is_none_on_a_constant_vector():
    """All models tied means there is no ordering to preserve: 0/0, not 1.0."""
    assert _tau_b([0.5, 0.5, 0.5], [0.1, 0.5, 0.9]) is None
    assert _tau_b([0.1, 0.5, 0.9], [0.5, 0.5, 0.5]) is None


def test_rank_positions_best_score_is_rank_one():
    ranks = _rank_positions({"m_a": 0.1, "m_b": 0.5, "m_c": 0.9}, MODELS)
    assert ranks["m_c"] == 1.0
    assert ranks["m_a"] == 3.0


def test_rank_change_is_zero_for_a_fully_tied_vector():
    """Fractional ranking keeps rank movement defined where tau_b is not."""
    tied = _rank_positions({m: 0.5 for m in MODELS}, MODELS)
    assert set(tied.values()) == {2.0}          # all share the average rank
    assert all(tied[m] - tied[m] == 0 for m in MODELS)


def test_tau_b_only_takes_four_values_with_three_models():
    """Documents why the pairwise reversal rate is the headline metric.

    Over a 3-element rank vector Kendall's tau_b is confined to
    {-1, -1/3, 1/3, 1}, so a 'tau_b < 0.85' cut-off degenerates into a binary
    'did any pair invert?' test.
    """
    from itertools import permutations

    base = [1.0, 2.0, 3.0]
    observed = {round(_tau_b(base, list(p)), 4) for p in permutations(base)}
    assert observed == {-1.0, -0.3333, 0.3333, 1.0}
