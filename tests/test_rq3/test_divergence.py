"""Tests for RQ3 divergence and the majority-vote consensus it feeds to RQ4."""

from meta_real_eval.rq3.divergence import ERROR_OUTPUT, _build_consensus, compute_divergence


def _sols(n):
    return [{"relation": f"r{i}", "model": "m", "passes_benchmark": True} for i in range(n)]


# ---------------------------------------------------------------------------
# End-to-end divergence (executes real subprocesses)
# ---------------------------------------------------------------------------

def _completions(bodies):
    """{relation: {model: [completion]}} — one solution per relation."""
    return {f"r{i}": {"m": [body]} for i, body in enumerate(bodies)}


def test_identical_solutions_do_not_diverge(simple_task):
    result = compute_divergence(
        simple_task,
        _completions(["    return a + b\n"] * 3),
        n_shared_inputs=5,
        timeout_s=10.0,
    )
    assert result["n_solutions"] == 3
    assert result["pairwise_disagreement_rate"] == 0.0


def test_divergent_solutions_are_detected(simple_task):
    result = compute_divergence(
        simple_task,
        _completions(["    return a + b\n", "    return a - b\n"]),
        n_shared_inputs=5,
        timeout_s=10.0,
    )
    assert result["n_solutions"] == 2
    assert result["pairwise_disagreement_rate"] > 0


def test_single_solution_returns_an_empty_consensus(simple_task):
    result = compute_divergence(
        simple_task, _completions(["    return a + b\n"]), n_shared_inputs=5, timeout_s=10.0
    )
    assert result["consensus"]["n_inputs_with_consensus"] == 0


# ---------------------------------------------------------------------------
# Consensus construction (pure, no subprocesses)
# ---------------------------------------------------------------------------

def test_unanimous_outputs_become_the_consensus():
    consensus, per_solution = _build_consensus(
        _sols(3), [(1,), (2,)], [["10", "20"], ["10", "20"], ["10", "20"]]
    )
    assert consensus["n_inputs_with_consensus"] == 2
    assert [e["expected_repr"] for e in consensus["entries"]] == ["10", "20"]
    assert all(r["consensus_disagreement_rate"] == 0.0 for r in per_solution)


def test_minority_output_counts_as_disagreement():
    consensus, per_solution = _build_consensus(
        _sols(5), [(1,)], [["10"], ["10"], ["10"], ["10"], ["99"]]
    )
    assert consensus["n_inputs_with_consensus"] == 1
    assert per_solution[4]["consensus_disagreement_rate"] == 1.0
    assert per_solution[0]["consensus_disagreement_rate"] == 0.0


def test_split_vote_yields_no_consensus():
    """2-vs-1 is a strict majority but not leave-one-out safe, so it is dropped."""
    consensus, _ = _build_consensus(_sols(3), [(1,)], [["10"], ["10"], ["99"]])
    assert consensus["n_inputs_with_consensus"] == 0


def test_fewer_than_three_voters_yields_no_consensus():
    consensus, _ = _build_consensus(_sols(2), [(1,)], [["10"], ["10"]])
    assert consensus["n_inputs_with_consensus"] == 0


def test_errors_never_vote_and_never_become_expected():
    """Three agreeing solutions plus one crash: the crash is a disagreement."""
    consensus, per_solution = _build_consensus(
        _sols(4), [(1,)], [["10"], ["10"], ["10"], [ERROR_OUTPUT]]
    )
    assert consensus["entries"][0]["expected_repr"] == "10"
    assert consensus["entries"][0]["n_voters"] == 3
    assert per_solution[3]["consensus_disagreement_rate"] == 1.0


def test_all_errors_yield_no_consensus():
    consensus, _ = _build_consensus(
        _sols(3), [(1,)], [[ERROR_OUTPUT], [ERROR_OUTPUT], [ERROR_OUTPUT]]
    )
    assert consensus["n_inputs_with_consensus"] == 0


def test_non_literal_output_never_becomes_a_consensus_value():
    """A repr like '<Foo object at 0x7f>' is not embeddable in generated code."""
    junk = "<Foo object at 0x7f>"
    consensus, _ = _build_consensus(_sols(3), [(1,)], [[junk], [junk], [junk]])
    assert consensus["n_inputs_with_consensus"] == 0


def test_crashing_majority_blocks_a_degenerate_consensus():
    """Regression: an input where most solutions legitimately raise.

    Errors do not vote, but they must still count in the denominator — otherwise
    the two solutions that silently return None here would define 'None' as the
    expected value, and every correct candidate would fail the assertion.
    """
    outputs = [[ERROR_OUTPUT]] * 5 + [["None"], ["None"]]
    consensus, _ = _build_consensus(_sols(7), [([],)], outputs)
    assert consensus["n_inputs_with_consensus"] == 0


# ---------------------------------------------------------------------------
# Representative-solution pick
# ---------------------------------------------------------------------------

def test_cached_pass_flags_pick_the_first_passing_completion(simple_task):
    """RQ2 already ran these completions; RQ3 must not re-execute them."""
    from meta_real_eval.rq3.divergence import _pick_best_completion
    comps = ["wrong-a", "wrong-b", "right"]
    best, passes = _pick_best_completion(
        comps, simple_task, timeout_s=10.0, pass_flags=[False, False, True]
    )
    assert (best, passes) == ("right", True)


def test_cached_flags_all_false_returns_the_first_and_labels_it_failing(simple_task):
    from meta_real_eval.rq3.divergence import _pick_best_completion
    best, passes = _pick_best_completion(
        ["a", "b"], simple_task, timeout_s=10.0, pass_flags=[False, False]
    )
    assert (best, passes) == ("a", False)


def test_mismatched_flag_length_falls_back_to_executing(simple_task):
    """A stale/short label vector must not be silently zipped against."""
    from meta_real_eval.rq3.divergence import _pick_best_completion
    best, passes = _pick_best_completion(
        ["    return a + b\n"], simple_task, timeout_s=10.0, pass_flags=[False, False]
    )
    assert passes is True          # executed, and it really does pass
