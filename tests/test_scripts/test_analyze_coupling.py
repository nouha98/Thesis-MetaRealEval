"""scripts/analyze_coupling.py on synthetic detection files: input conversion (task-level masking,
the stored-P fallback), the technical report, the endpoint pipeline, and the freeze guard."""

import random
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyze_coupling as ac  # noqa: E402


def det(task, seed):
    rng = random.Random(seed)
    tests = {f"p:t{i}": "p" for i in range(2)} | {f"gen:gen_{i}": "gen" for i in range(12)}
    ids = sorted(tests)
    pert = [f"x:test_{i}" for i in range(2)] + [f"x:test_0~p{i}" for i in range(4)]

    def cells(pool_ids):
        return {"detect": rng.sample(pool_ids, rng.randint(1, len(pool_ids) - 1)), "masked": [], "import_error": False}
    progs = []
    for i in range(4):
        progs.append({"kind": "mutant", "id": f"m{i}", "source": ["operator", "llm_whole"][i % 2],
                      "models": [] if i % 2 == 0 else ["B"], "historical_killed": True, "p_passed_all": None,
                      "primary": cells(ids), "perturbed": cells(pert)})
    for i in range(5):
        progs.append({"kind": "solution", "id": f"s{i}", "models": ["A"],
                      "members": [{"relation": "original", "model": "A", "index": i, "stored_p_pass": i % 2 == 0}],
                      "p_passed_all": None, "primary": cells(ids), "perturbed": cells(pert)})
    return {"task": task, "support": {"supported": True}, "seconds": 1.0, "solution_groups_digest": "d",
            "spec_sha256": "s", "tests": {"primary": tests, "perturbed": pert}, "programs": progs}


def test_inputs_drop_masked_tests_for_the_whole_task_and_use_stored_p():
    d = det("T", 0)
    d["programs"][0]["primary"]["masked"] = ["p:t0"]
    tests, muts, sols, n_masked = ac.inputs(d)
    assert n_masked == 1 and "p:t0" not in tests and all("p:t0" not in m["detect"] for m in muts)
    assert [s["p_pass"] for s in sols] == [True, False, True, False, True]
    tests40, *_ = ac.inputs(d, gen_limit=5)
    assert sum(s == "gen" for s in tests40.values()) == 5


def test_technical_report_has_no_coupling_value():
    res = ac.technical([det("T", 1), det("U", 2)])
    assert res["tasks"] == 2 and res["cell_agreement"] == 1.0
    assert res["perturbed_false_detection_on_p_passing"] is not None
    flat = repr(res)
    assert "lift" not in flat and "'pc'" not in flat and "means" not in flat


def test_endpoints_run_end_to_end_and_exclude_development_tasks():
    dets = [det(f"T{i}", i) for i in range(6)]
    res = ac.endpoints(dets, dev={"T0"})
    assert len(res["per_task"]) == 5
    assert res["power_rule"]["min_tasks"] == 30 and res["power_rule"]["confirmatory"] is False
    assert set(res["sensitivity"]) == {"perturbed_pool", "pool_size_40", "total_failures_included",
                                       "unstratified_null", "no_deduplication", "unequalised_max"}


def test_endpoints_refuse_without_a_frozen_spec(tmp_path, monkeypatch):
    monkeypatch.setattr(ac, "FROZEN", tmp_path / "coupling_v1.json")
    assert ac.frozen_ok([det("T", 0)]) == ["coupling_v1.json is not frozen yet"]


def _with_reference(d, primary_detect=(), perturbed_detect=()):
    d["programs"].insert(0, {"kind": "reference", "id": "reference", "p_passed_all": True,
                             "primary": {"detect": list(primary_detect), "masked": [], "import_error": False},
                             "perturbed": {"detect": list(perturbed_detect), "masked": [], "import_error": False}})
    return d


def test_reference_row_is_not_a_program_and_its_unstable_tests_are_dropped():
    d = _with_reference(det("T", 3), perturbed_detect=["x:test_1"])
    tests, muts, sols, _ = ac.inputs(d)
    assert len(muts) == 4 and len(sols) == 5 and all(s["id"] != "reference" for s in sols)
    ptests, pmuts, *_ = ac.inputs(d, "perturbed")
    assert "x:test_1" not in ptests and all("x:test_1" not in m["detect"] for m in pmuts)
    res = ac.technical([d, _with_reference(det("U", 4))])
    assert res["reference_rows"]["clean"] == 1 and res["reference_rows"]["problems"] == {"T": ["perturbed.detect: 1"]}
    assert res["reference_rows"]["unstable_tests_dropped"] == {"primary": 0, "perturbed": 1}


def test_endpoints_refuse_supported_tasks_on_unreviewed_contracts(tmp_path, monkeypatch):
    import hashlib
    import json
    f = tmp_path / "coupling_v1.json"
    sha = hashlib.sha256(json.dumps(ac.SPEC, sort_keys=True).encode()).hexdigest()
    f.write_text(json.dumps({"spec_sha256": sha, "solution_groups": {"T": "d"}}), encoding="utf-8")
    monkeypatch.setattr(ac, "FROZEN", f)
    d = det("T", 0) | {"spec_sha256": sha, "contract": {"status": "draft"}}
    assert any("unreviewed contract" in p for p in ac.frozen_ok([d]))
    d["contract"]["status"] = "reviewed"
    assert ac.frozen_ok([d]) == []
