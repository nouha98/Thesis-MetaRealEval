"""scripts/validate_realclasseval.py: a task with an empty or unparseable skeleton is never accepted."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("validate_realclasseval",
                                              REPO / "scripts" / "validate_realclasseval.py")
gate = importlib.util.module_from_spec(spec)
sys.modules["validate_realclasseval"] = gate
spec.loader.exec_module(gate)


def test_an_accepted_task_with_an_invalid_skeleton_is_excluded():
    tasks = [SimpleNamespace(prompt="class A:\n    pass\n"), SimpleNamespace(prompt="  \n"),
             SimpleNamespace(prompt="class B:\n    def f(self, x: Tuple[int,\n"),
             SimpleNamespace(prompt="")]
    records = [{"status": "accepted"}, {"status": "accepted"}, {"status": "accepted"},
               {"status": "excluded", "exclusion_reason": "gate_error"}]
    gate.exclude_invalid_skeletons(tasks, records)
    assert records[0] == {"status": "accepted"}
    assert records[1] == {"status": "excluded", "exclusion_reason": "empty_skeleton"}
    assert records[2] == {"status": "excluded", "exclusion_reason": "unparseable_skeleton"}
    assert records[3]["exclusion_reason"] == "gate_error"     # an earlier verdict is kept


def test_the_corpus_has_exactly_the_known_invalid_skeletons():
    from meta_real_eval.benchmarks.realclasseval import RealClassEvalBenchmark
    corpus = REPO / "data" / "realclasseval" / "realclasseval_v1.jsonl.gz"
    if not corpus.is_file():
        pytest.skip("corpus not staged")
    found: dict[str, list[str]] = {}
    for t in RealClassEvalBenchmark(corpus_path=corpus).corpus_tasks():
        defect = gate.skeleton_defect(t.prompt)
        if defect:
            found.setdefault(defect, []).append(t.label)
    assert sorted(found["empty_skeleton"]) == [
        "RCE_csn_snippet_122", "RCE_csn_snippet_238", "RCE_csn_snippet_4", "RCE_post_snippet_356"]
    assert sorted(found["unparseable_skeleton"]) == sorted(
        [f"RCE_csn_snippet_{i}" for i in (74, 80, 143)]
        + [f"RCE_post_snippet_{i}" for i in (26, 81, 87, 133, 269, 276, 310, 333, 344)])
