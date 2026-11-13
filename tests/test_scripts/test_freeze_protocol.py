"""scripts/freeze_protocol.py: the frozen audit order and the RQ1 robustness group logic."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import analyze_rq1_witness as ar  # noqa: E402
import freeze_protocol as fp  # noqa: E402


def test_audit_order_is_a_seeded_stratified_permutation():
    labels = [f"csn_{i}" for i in range(30)] + [f"post_{i}" for i in range(20)]
    split_of = {x: x.split("_")[0] for x in labels}
    a, b = fp.audit_order(labels, split_of, 7), fp.audit_order(labels, split_of, 7)
    assert a == b and sorted(a) == sorted(labels)
    assert fp.audit_order(labels, split_of, 8) != a
    for k in (10, 20, 30):                         # every prefix keeps the 60/40 shares (+-1)
        assert abs(sum(x.startswith("csn") for x in a[:k]) - 0.6 * k) <= 1


def _g(source, outcome, killed, level="api_visible", domain="valid", eq="no_divergence"):
    return {"source": source, "outcome": outcome, "level": level, "domain": domain,
            "replay": {"confirmed": outcome == "distinguished"},
            "members": [{"record_id": "x", "killed": killed, "equivalence": eq}]}


def test_rq1_populations_at_group_level():
    res = {"task": "T", "support": {"supported": True}, "gated": False, "contract": {"status": "draft"},
           "groups": [_g("operator", "distinguished", True, eq="diverged"),
                      _g("operator", "distinguished", False),                  # new witness, survives P
                      _g("llm_whole", "unresolved", False),
                      _g("llm_whole", "distinguished", False, level="private_state_only"),
                      _g("mixed", "distinguished", False, eq="diverged")]}
    out = ar.analyse([res])["populations"]
    assert out["historical"]["operator"]["groups"] == 2 and out["historical"]["llm_whole"]["groups"] == 1
    assert out["primary"]["operator"] == {"killed": 1, "groups": 3, "kill_rate": 1 / 3}
    assert out["primary"]["llm_whole"]["groups"] == 1                          # the mixed group
    assert out["full_trace"]["llm_whole"]["groups"] == 2
    assert out["bound_unresolved"]["llm_whole"]["groups"] == 2
