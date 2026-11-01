"""scripts/gate_c.py: verdicts carry over on identical text only; apply re-hashes."""

import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("gate_c", REPO / "scripts" / "gate_c.py")
gate_c = importlib.util.module_from_spec(spec)
sys.modules["gate_c"] = gate_c
spec.loader.exec_module(gate_c)

from meta_real_eval.rq2.corpus import tasks_sha256, verify_corpus  # noqa: E402

PILOT2_SHEET = REPO / "doc" / "gate_c" / "realclasseval_pilot2.review_sheet.md"


def _variant(family: str, text: str) -> dict:
    return {"variant_id": f"llm_{family}_01", "family": family, "text": text,
            "validation": {"judge_verdict": "EQUIVALENT", "judge_reason": "same"}}


def _corpus(path: Path, tasks: dict) -> dict:
    corpus = {"manifest": {"families": ["lexical", "formal", "terse"], "n_per_family": 1},
              "tasks": tasks}
    corpus["manifest"]["sha256"] = tasks_sha256(corpus)
    path.write_text(json.dumps(corpus), encoding="utf-8")
    return corpus


def _fill(sheet: Path, verdicts: dict[int, str]) -> None:
    doc = sheet.read_text(encoding="utf-8")
    for n, verdict in verdicts.items():
        doc = doc.replace(f"| {n} |  |  |", f"| {n} | {verdict} | note {n} |")
    sheet.write_bytes(doc.replace("\n", "\r\n").encode("utf-8"))   # edited on Windows


def test_a_pilot2_sheet_parses_to_its_72_verdicts():
    items = gate_c.parse_sheet(PILOT2_SHEET)
    assert len(items) == 72
    assert sorted(i["n"] for i in items if i["verdict"] == "reject") == [1, 3, 20, 30, 42, 52, 61, 71]
    assert all(i["verdict"] for i in items)


def test_sheet_then_apply_removes_only_identical_rejected_text(tmp_path):
    a, b = "class A:\n    '''Hold.'''\n", "class B:\n    '''Keep.'''\n"
    first = tmp_path / "first.json"
    _corpus(first, {"T/a": {"original": a, "variants": [_variant("lexical", a + "# x\n"),
                                                         _variant("terse", a + "# y\n")]},
                    "T/b": {"original": b, "variants": [_variant("formal", b + "# z\n")]}})
    sheet1 = tmp_path / "first.review_sheet.md"
    assert gate_c.main(["sheet", "--corpus", str(first), "--n", "3", "--out", str(sheet1)]) == 0
    items = gate_c.parse_sheet(sheet1)
    rejected = next(i for i in items if i["variant_id"] == "llm_lexical_01")
    _fill(sheet1, {i["n"]: "not equivalent" if i is rejected else "equivalent (minor)" for i in items})

    # a later corpus: lexical replayed identically, terse regenerated, one new task
    later = tmp_path / "later.json"
    _corpus(later, {"T/a": {"original": a, "variants": [_variant("lexical", a + "# x\n"),
                                                        _variant("terse", a + "# NEW\n")]},
                    "T/b": {"original": b, "variants": [_variant("formal", b + "# z\n")]},
                    "T/c": {"original": b, "variants": [_variant("lexical", b + "# c\n")]}})
    groups = gate_c.classify(json.loads(later.read_text()), gate_c.parse_sheet(sheet1))
    assert {k: len(v) for k, v in groups.items()} == {
        "accepted": 1, "rejected": 1, "changed": 1, "unreviewed": 1}

    # the rejected text under another task or another family inherits nothing
    elsewhere = {"tasks": {"T/x": {"original": a, "variants": [_variant("lexical", a + "# x\n")]},
                           "T/a": {"original": a, "variants": [_variant("formal", a + "# x\n")]}}}
    assert {k: len(v) for k, v in gate_c.classify(elsewhere, gate_c.parse_sheet(sheet1)).items()} == {
        "accepted": 0, "rejected": 0, "changed": 0, "unreviewed": 2}

    sheet2 = tmp_path / "later.review_sheet.md"
    gate_c.main(["sheet", "--corpus", str(later), "--reviewed", str(sheet1), "--n", "0",
                 "--out", str(sheet2)])
    assert [(i["task_id"], i["variant_id"]) for i in gate_c.parse_sheet(sheet2)] == [
        ("T/a", "llm_terse_01")], "a changed slot is always re-reviewed"

    assert gate_c.main(["apply", "--corpus", str(later), "--sheet", str(sheet1)]) == 0
    out = json.loads(later.read_text(encoding="utf-8"))
    assert [v["variant_id"] for v in out["tasks"]["T/a"]["variants"]] == ["llm_terse_01"]
    verify_corpus(out, out["manifest"]["sha256"], later)
    assert out["manifest"]["gate_c"]["removed"] == [
        {"task_id": "T/a", "variant_id": "llm_lexical_01", "note": f"note {rejected['n']}",
         "sheet": sheet1.name}]
    before = out["manifest"]["gate_c"]["sha256_before"]

    gate_c.main(["apply", "--corpus", str(later), "--sheet", str(sheet1)])   # idempotent
    again = json.loads(later.read_text(encoding="utf-8"))
    assert again["manifest"]["sha256"] == out["manifest"]["sha256"]
    assert again["manifest"]["gate_c"]["sha256_before"] == before
    assert len(again["manifest"]["gate_c"]["removed"]) == 1
