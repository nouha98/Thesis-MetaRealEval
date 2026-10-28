"""rq2/corpus.py on RealClassEval class skeletons: the docstring splice and its gates."""

import ast
import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

from meta_real_eval.rq2.corpus import (
    FAMILIES,
    MIN_FAMILIES_COVERED,
    assemble_docstrings,
    class_candidate,
    class_structural_gate,
    docstring_texts,
    generate_family,
    min_families_covered,
    parse_segments,
    render_docstring,
    split_docstrings,
)

REPO = Path(__file__).resolve().parents[2]
CORPUS = REPO / "data" / "realclasseval" / "realclasseval_v1.jsonl.gz"

SKELETON = (
    "import os\n\n\n"
    "class Cache:\n"
    '    """A small cache that stores at most 3 items."""\n\n'
    "    def __init__(self, path: str='é'):\n"
    '        """\n'
    "        Open the cache stored at path.\n\n"
    "        >>> Cache('x').path\n"
    "        'x'\n"
    '        """\n'
    "        pass\n\n"
    "    def get(self, key):\n"
    "        r'''Return the value for key, or None.'''\n"
    "        pass\n"
)


def _raw(segments: list[str]) -> str:
    return "\n".join(f"<<<{i}>>>\n{s}" for i, s in enumerate(segments, start=1))


def _reworded(skeleton: str) -> list[str]:
    return ["Reworded. " + inspect.cleandoc(t) for t in docstring_texts(skeleton)]


def _parseable_corpus_skeletons():
    from meta_real_eval.benchmarks.realclasseval import RealClassEvalBenchmark
    import importlib.util
    spec = importlib.util.spec_from_file_location("vr", REPO / "scripts" / "validate_realclasseval.py")
    vr = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vr)
    return [t for t in RealClassEvalBenchmark(corpus_path=CORPUS).corpus_tasks()
            if vr.skeleton_defect(t.prompt) is None]


# --- the splice -------------------------------------------------------------

def test_spans_cover_every_docstring_in_source_order():
    texts = docstring_texts(SKELETON)
    assert len(texts) == 3
    assert texts[0] == "A small cache that stores at most 3 items."
    assert texts[2] == "Return the value for key, or None."
    assert assemble_docstrings(SKELETON, texts) == SKELETON


@pytest.mark.skipif(not CORPUS.is_file(), reason="corpus not staged")
def test_round_trip_is_byte_exact_on_every_parseable_corpus_skeleton():
    tasks = _parseable_corpus_skeletons()
    assert len(tasks) == 476
    for t in tasks:
        texts = docstring_texts(t.prompt)
        assert texts, f"{t.label}: no docstring found"
        assert assemble_docstrings(t.prompt, texts) == t.prompt, t.label


@pytest.mark.skipif(not CORPUS.is_file(), reason="corpus not staged")
def test_gate_accepts_a_neutral_rewrite_on_representative_corpus_skeletons():
    tasks = _parseable_corpus_skeletons()
    sample = tasks[::32]                                  # 15 skeletons across both splits
    assert len(sample) == 15
    assert any(any(ord(c) > 127 for c in t.prompt) for t in tasks)
    for t in sample:
        candidate, reason = class_candidate(t.prompt, _raw(_reworded(t.prompt)))
        assert reason is None, (t.label, reason)
        assert class_structural_gate(t.prompt, candidate) is None, t.label


def test_render_keeps_the_original_layout():
    multi = "\n        Open the cache.\n\n        More.\n        "
    assert render_docstring("New text.\n\nMore here.", multi, "        ") == (
        "\n        New text.\n\n        More here.\n        ")
    assert render_docstring("One line.", "Old one line.", "    ") == "One line."


# --- the candidate and Gate A -----------------------------------------------

def test_a_reworded_candidate_passes_and_only_docstrings_change():
    candidate, reason = class_candidate(SKELETON, _raw(_reworded(SKELETON)))
    assert reason is None
    assert class_structural_gate(SKELETON, candidate) is None
    assert "Reworded. Open the cache stored at path." in candidate
    assert "def __init__(self, path: str='é'):" in candidate          # non-ASCII code intact
    assert "        >>> Cache('x').path\n        'x'\n" in candidate    # example kept, re-indented


@pytest.mark.parametrize("raw,reason", [
    ("<<<1>>>\na\n<<<2>>>\nb\n", "segment_count_mismatch"),
    ("Sure! Here it is.\n<<<1>>>\na\n<<<2>>>\nb\n<<<3>>>\nc\n", "text_before_segments"),
    ("<<<1>>>\na\n<<<2>>>\n   \n<<<3>>>\nc\n", "empty_segment"),
    ("<<<1>>>\na\n<<<3>>>\nb\n<<<2>>>\nc\n", "segment_count_mismatch"),
])
def test_malformed_responses_are_rejected(raw, reason):
    assert class_candidate(SKELETON, raw) == (None, reason)


def _gate(segments: list[str], **kw):
    candidate, reason = class_candidate(SKELETON, _raw(segments))
    return reason or class_structural_gate(SKELETON, candidate, **kw)


def test_gate_rejects_identical_duplicate_numbers_examples_and_broken_literals():
    same = [inspect.cleandoc(t) for t in docstring_texts(SKELETON)]
    assert _gate(same) == "identical_to_original"
    ok = _reworded(SKELETON)
    first, _ = class_candidate(SKELETON, _raw(ok))
    from meta_real_eval.rq2.corpus import _normalize
    assert _gate(ok, seen={_normalize(first)}) == "duplicate_of_sibling"
    assert _gate([ok[0] + " At most 7.", ok[1], ok[2]]).startswith("new_numeric_literal")
    changed = ok[1].replace("'x'\n", "'y'\n") if "'x'\n" in ok[1] else ok[1][:-3] + "'y'"
    assert _gate([ok[0], changed, ok[2]]) == "examples_changed"
    assert _gate([ok[0] + ' """ + x', ok[1], ok[2]]) in ("does_not_parse", "code_changed",
                                                           "docstring_count_changed")


def test_family_threshold_is_all_but_one():
    assert min_families_covered(FAMILIES) == MIN_FAMILIES_COVERED == 4
    assert min_families_covered(["lexical", "formal", "terse"]) == 2


def test_parse_segments_round_trip():
    assert parse_segments(_raw(["a", "b c"]), 2) == (["a", "b c"], None)


# --- generate_family's class path -------------------------------------------

class _FakeClient:
    """Generator returns one good and one malformed candidate; the judge agrees."""

    def __init__(self):
        self.calls = []

    async def complete(self, model, messages, **kw):
        self.calls.append((model, messages))
        if model == "judge":
            assert "class skeleton" in messages[0]["content"]
            return ["EQUIVALENT\nsame contract"]
        return [_raw(_reworded(SKELETON)), "no segments at all"]


def test_generate_family_rewrites_a_class_skeleton():
    task = SimpleNamespace(task_id="RealClassEval/csn/snippet_0", prompt=SKELETON, target="Cache")
    client = _FakeClient()
    accepted, rejected = asyncio.run(generate_family(task, "lexical", "gen", "judge", client,
                                                     n_per_family=1))
    assert [a["variant_id"] for a in accepted] == ["llm_lexical_01"]
    assert ast.parse(accepted[0]["text"])
    gen_messages = client.calls[0][1]
    assert "<<<1>>>" in gen_messages[1]["content"] and "CONTEXT" in gen_messages[1]["content"]
    assert rejected == [], "the slot was filled by the first candidate; the second is never read"
