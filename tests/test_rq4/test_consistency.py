"""Regression tests for the MT consistency assertions.

These exist because the augmentation used to be a silent no-op: it emitted a
`def _check_consistency(*fns)` that nothing ever called, so the "MT-augmented"
suite behaved exactly like the plain degraded suite and H1a could only ever
come back null. The decisive property is therefore behavioural — the generated
code must actually FAIL a wrong candidate and PASS a correct one.
"""

from meta_real_eval.core.sandbox import execute
from meta_real_eval.rq4.consistency import build_consistency_assertions


def _divergence(entries, rate=0.9, n_solutions=5):
    return {
        "pairwise_disagreement_rate": rate,
        "n_solutions": n_solutions,
        "consensus": {"entries": entries},
    }


def _entries():
    """Consensus: add(1, 2) == 3 and add(-1, 1) == 0, both unanimous."""
    return [
        {"args_repr": "(1, 2)", "expected_repr": "3", "votes": 5, "n_voters": 5},
        {"args_repr": "(-1, 1)", "expected_repr": "0", "votes": 4, "n_voters": 5},
    ]


def _run(simple_task, ca_code, solution_body):
    solution = simple_task.prompt + solution_body
    return execute(solution, ca_code, timeout_s=10.0)


def test_correct_candidate_passes(simple_task):
    code, n = build_consistency_assertions(simple_task, _divergence(_entries()), threshold=0.1)
    assert n == 2
    assert _run(simple_task, code, "    return a + b\n").passed


def test_wrong_candidate_fails(simple_task):
    code, _ = build_consistency_assertions(simple_task, _divergence(_entries()), threshold=0.1)
    result = _run(simple_task, code, "    return a - b\n")
    assert not result.passed
    assert "Consistency violation" in result.stderr


def test_below_threshold_emits_nothing(simple_task):
    """Solutions that already agree need no cross-variant check."""
    code, n = build_consistency_assertions(
        simple_task, _divergence(_entries(), rate=0.01), threshold=0.1
    )
    assert (code, n) == ("", 0)


def test_too_few_reference_solutions_emits_nothing(simple_task):
    """A majority vote is undefined below three reference solutions."""
    code, n = build_consistency_assertions(
        simple_task, _divergence(_entries(), n_solutions=2), threshold=0.1
    )
    assert (code, n) == ("", 0)


def test_no_consensus_inputs_emits_nothing(simple_task):
    code, n = build_consistency_assertions(simple_task, _divergence([]), threshold=0.1)
    assert (code, n) == ("", 0)


def test_uncalibrated_threshold_uses_documented_default(simple_task):
    """threshold=None must not silently disable the check; it falls back to 0.1."""
    code, n = build_consistency_assertions(simple_task, _divergence(_entries()), threshold=None)
    assert n == 2
    assert code


def test_assertions_are_capped(simple_task):
    entries = _entries() * 20
    _, n = build_consistency_assertions(
        simple_task, _divergence(entries), threshold=0.1, max_assertions=5
    )
    assert n == 5


def test_uncompilable_expected_value_yields_nothing(simple_task):
    """The emitted block is prepended to every candidate's run: a syntax error
    there would fail all of them and look exactly like a real MT effect."""
    bad = [{"args_repr": "(1, 2)", "expected_repr": "<Foo object at 0x7f>",
            "votes": 5, "n_voters": 5}]
    code, n = build_consistency_assertions(simple_task, _divergence(bad), threshold=0.1)
    assert (code, n) == ("", 0)
