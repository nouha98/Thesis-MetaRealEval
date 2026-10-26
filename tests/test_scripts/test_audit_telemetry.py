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


def test_legacy_cells_read_the_last_successful_attempt():
    legacy = {"status": "ok", "attempts": [
        {"attempt": 1, "error": "x"},
        {"attempt": 2, "request": {"usage": {"completion_tokens": 7}, "choices": []},
         "records": [{"finish_reason": "stop", "disposition": "answer"}]}]}
    [row] = audit.telemetry({"m": [legacy]})
    assert row["completion_tokens_per_request"]["median"] == 7 and row["choices"] == 1
