"""scripts/coupling_recompute.py (no project imports) must agree with the analysis on synthetic runs."""

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import analyze_coupling as ac  # noqa: E402
import coupling_recompute as cr  # noqa: E402
from test_analyze_coupling import det  # noqa: E402


def test_independent_recompute_matches_the_analysis():
    dets = [det(f"T{i}", i) for i in range(8)]
    rows = {r["task"]: r for r in ac.endpoints(dets, dev=set())["per_task"] if r["excluded"] is None}
    assert rows
    for d in dets:
        if d["task"] not in rows:
            continue
        mine, theirs = cr.recompute(d, ac.SPEC["version"], ac.SPEC["null_permutations"]), rows[d["task"]]
        assert mine["exact"] and mine["n_contributing"] == theirs["n_contributing"]
        for src in ("operator", "llm_whole"):
            for key in cr.KEYS:
                assert abs(mine["means"][src][key] - theirs["means"][src][key]) < 1e-9, (d["task"], src, key)
