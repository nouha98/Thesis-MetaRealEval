"""Tests for RQ3 divergence and the unanimous consensus it feeds to RQ4."""

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
    assert result["pairwise_disagreement_rate"] is None


def test_two_crashing_solutions_do_not_count_as_agreeing(simple_task):
    """A crash means "unknown", so a pair of crashes is no evidence of agreement.

    Comparing the error sentinels as values made broken solutions agree with
    each other and disagree with every working one, so the rate tracked how many
    solutions were broken rather than how far the working ones diverged. On the
    pre-repair corpus 72 of 164 tasks scored exactly g(n-g)/C(n,2) -- the
    algebraic signature of that artifact.
    """
    result = compute_divergence(
        simple_task,
        _completions(["    raise ValueError('boom')\n"] * 2),
        n_shared_inputs=5,
        timeout_s=10.0,
    )
    assert result["n_comparable_pairs"] == 0
    assert result["n_pairs_excluded_error"] > 0
    # None, not 0.0: nothing was comparable, so there is no evidence either way.
    assert result["pairwise_disagreement_rate"] is None


def test_a_crashing_solution_does_not_inflate_divergence(simple_task):
    """Two agreeing solutions plus one that always crashes still read as 0."""
    result = compute_divergence(
        simple_task,
        _completions([
            "    return a + b\n",
            "    return a + b\n",
            "    raise ValueError('boom')\n",
        ]),
        n_shared_inputs=5,
        timeout_s=10.0,
    )
    assert result["pairwise_disagreement_rate"] == 0.0
    assert result["n_pairs_excluded_error"] > 0


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


def test_a_lone_dissenter_destroys_the_consensus():
    """4-of-5 is a clear majority, and it is still not enough.

    RQ4 turns a kept entry into an assertion every candidate must satisfy, so a
    wrong entry does not add noise -- it fails correct solutions. One reference
    disagreeing is evidence that the references do not actually know what this
    input should produce, so nothing is asserted about it.
    """
    consensus, per_solution = _build_consensus(
        _sols(5), [(1,)], [["10"], ["10"], ["10"], ["10"], ["99"]]
    )
    assert consensus["n_inputs_with_consensus"] == 0


def test_split_vote_yields_no_consensus():
    consensus, _ = _build_consensus(_sols(3), [(1,)], [["10"], ["10"], ["99"]])
    assert consensus["n_inputs_with_consensus"] == 0


def test_fewer_than_three_voters_yields_no_consensus():
    consensus, _ = _build_consensus(_sols(2), [(1,)], [["10"], ["10"]])
    assert consensus["n_inputs_with_consensus"] == 0


def test_errors_never_vote_and_never_become_expected():
    """Nine agreeing solutions plus one crash: the crash is a disagreement.

    Sized so the voter-share rule is comfortably satisfied (9/10) and this test
    isolates the error-handling behaviour rather than the share threshold.
    """
    consensus, per_solution = _build_consensus(
        _sols(10), [(1,)], [["10"]] * 9 + [[ERROR_OUTPUT]]
    )
    assert consensus["entries"][0]["expected_repr"] == "10"
    assert consensus["entries"][0]["n_voters"] == 9
    assert per_solution[9]["consensus_disagreement_rate"] == 1.0
    assert per_solution[0]["consensus_disagreement_rate"] == 0.0


def test_too_few_solutions_produced_a_value_to_trust_their_agreement():
    """Unanimity among survivors is weak when most references crashed.

    An input that crashes most solutions is usually outside the task's domain,
    which is exactly where a confident-looking consensus is most likely wrong.
    """
    outputs = [["None"]] * 3 + [[ERROR_OUTPUT]] * 7
    consensus, _ = _build_consensus(_sols(10), [(1,)], outputs)
    assert consensus["n_inputs_with_consensus"] == 0


# --- the three assertions that failed correct solutions on the real corpus ---
#
# Each was a majority, each became an assertion, and each failed a solution that
# passes the full benchmark. Pinned here as vote counts so the rule cannot
# regress back to admitting them.

def test_real_corpus_fib_negative_input_is_rejected():
    """HumanEval/55: fib(-72) == 0 on 14 of 17 voters (18 solutions).

    Became an assertion and dropped qwen3-next-80b from pass@1 1.0 to 0.0.
    """
    outputs = [["0"]] * 14 + [["1"]] * 3 + [[ERROR_OUTPUT]]
    consensus, _ = _build_consensus(_sols(18), [(-72,)], outputs)
    assert consensus["n_inputs_with_consensus"] == 0


def test_real_corpus_make_a_pile_negative_input_is_rejected():
    """HumanEval/100: make_a_pile(-72) == [] on 9 of 12 voters."""
    outputs = [["[]"]] * 9 + [["None"]] * 3
    consensus, _ = _build_consensus(_sols(12), [(-72,)], outputs)
    assert consensus["n_inputs_with_consensus"] == 0


def test_real_corpus_unanimous_in_domain_entry_survives():
    """The counterpart: fib(10) == 55 at 17/17 voters must still be kept.

    The rule has to stay usable -- excluding everything would disable RQ4's
    augmentation rather than fix it.
    """
    outputs = [["55"]] * 17 + [[ERROR_OUTPUT]]
    consensus, _ = _build_consensus(_sols(18), [(10,)], outputs)
    assert consensus["n_inputs_with_consensus"] == 1
    assert consensus["entries"][0]["expected_repr"] == "55"


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
