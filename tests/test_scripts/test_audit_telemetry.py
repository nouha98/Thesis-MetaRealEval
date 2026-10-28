"""scripts/audit_rq2_generation.py telemetry: unavailable is never zero."""

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("audit_rq2_generation",
                                              REPO / "scripts" / "audit_rq2_generation.py")
audit = importlib.util.module_from_spec(spec)
sys.modules["audit_rq2_generation"] = audit
spec.loader.exec_module(audit)


def _cell(tokens, reasoning_tokens, finish, latency, attempts=1, status="ok"):
    return {"status": status,
            "records": [{"finish_reason": f, "disposition": "answer" if f == "stop" else "truncated"}
                        for f in finish],
            "request": {"usage": None if tokens is None else {"completion_tokens": tokens},
                        "reasoning_tokens": reasoning_tokens,
                        "choices": [{"reasoning_field_chars": None} for _ in finish],
                        "success_latency_s": latency, "total_latency_s": latency * attempts,
                        "attempts": [{}] * attempts}}


def test_telemetry_counts_unavailable_values_separately():
    cells = [_cell(100, None, ["stop", "length"], 2.0),
             _cell(None, None, ["stop", "stop"], 4.0, attempts=2),
             {"status": "transport_failure", "error": "down"}]
    [row] = audit.telemetry({"m": cells})
    assert row["status"] == {"ok": 2, "transport_failure": 1}
    assert row["truncation_rate"] == 0.25
    assert row["completion_tokens_per_request"]["median"] == 100
    assert row["completion_tokens_per_request"]["unavailable"] == 1
    assert row["reasoning_tokens_per_request"] == {"median": None, "unavailable": 2}
    assert row["reasoning_field_chars_per_choice"]["unavailable"] == 4
    assert row["latency_s"]["requests_with_transport_retries"] == 1
    assert row["requests_without_meta"] == 1


def test_by_task_counts_truncation_and_unusable_per_cell(capsys):
    import collections
    counter = collections.Counter()
    audit.count_cell(_cell(100, None, ["stop", "length", "length"], 2.0), counter)
    audit.count_cell({"status": "transport_failure"}, counter)
    audit.count_cell({"records": [{"finish_reason": "length", "disposition": "unusable_reasoning_only"}]},
                     counter)
    assert (counter["choices"], counter["length"], counter["unusable"]) == (4, 3, 1)
    counter["failed"] = 1
    audit.print_by_task({("t1", "m"): counter})
    assert "3/1/1 of 4" in capsys.readouterr().out


def test_rq1_truncation_counts_length_and_unrecorded_attempts():
    meta = [{"m": {"attempts": [{"finish_reasons": ["stop", "length"]}, {"request": {}}]}},
            {"m": {"attempts": [{"finish_reasons": ["length"]}]}}]
    c = audit.rq1_truncation(meta)["m"]
    assert (c["choices"], c["length"], c["attempts_unrecorded"]) == (3, 2, 1)


def test_truncated_choices_report_disposition_and_a_loop_indicator():
    loop, prose = "abc " * 500, "".join(chr(65 + (i * 7919) % 58) for i in range(2000))
    cell = {"records": [{"finish_reason": "length", "disposition": "unusable_truncated"},
                        {"finish_reason": "stop", "disposition": "answer"},
                        {"finish_reason": "length", "disposition": "truncated"}],
            "request": {"choices": [{"answer_chars": 0, "reasoning_field_chars": 9, "reasoning_tail": loop},
                                    {"answer_chars": 5, "reasoning_field_chars": 3},
                                    {"answer_chars": 7, "reasoning_field_chars": 9, "reasoning_tail": prose}]}}
    rows = audit.truncated_choices("t", "original", "m", cell)
    assert [r["index"] for r in rows] == [0, 2]
    assert rows[0]["disposition"] == "unusable_truncated"
    assert rows[0]["tail_compression"] < rows[1]["tail_compression"], "a loop compresses better"
    old = {"records": [{"finish_reason": "length", "disposition": "truncated"}],
           "request": {"choices": [{"answer_chars": 1, "reasoning_field_chars": None}]}}
    assert audit.truncated_choices("t", "original", "m", old)[0]["tail_compression"] is None


def test_independence_counts_distinct_and_cross_arm_overlap():
    import collections
    out = collections.defaultdict(collections.Counter)
    audit.independence({"original": {"m": ["a", "a", "b"]},
                        "control_resample": {"m": ["b", "c", "d"]}}, out)
    assert (out["m"]["choices"], out["m"]["distinct"]) == (6, 5)
    assert (out["m"]["pairs"], out["m"]["shared_texts"]) == (1, 1)


def test_legacy_cells_read_the_last_successful_attempt():
    legacy = {"status": "ok", "attempts": [
        {"attempt": 1, "error": "x"},
        {"attempt": 2, "request": {"usage": {"completion_tokens": 7}, "choices": []},
         "records": [{"finish_reason": "stop", "disposition": "answer"}]}]}
    [row] = audit.telemetry({"m": [legacy]})
    assert row["completion_tokens_per_request"]["median"] == 7 and row["choices"] == 1
