"""Phase 1 of the saturation analysis: freeze and verify the final Tier 1 and Tier 2 results.

    python scripts/saturation_baseline.py            # freeze (first run), build views, verify
    python scripts/saturation_baseline.py --verify   # only re-hash and compare with the freeze

Writes results_saturation/baseline_manifest.json (+ per-file hashes), the read-only views, and
doc/saturation/baseline_verification.md. Nothing outside results_saturation/ and doc/saturation/
is written. Exit code 1 if any reproduction line fails: the simulation must not be run then.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import saturation_common as sc  # noqa: E402

MANIFEST = sc.OUT / "baseline_manifest.json"
FILE_HASHES = sc.OUT / "baseline_file_hashes.json"

TREES = {
    "tier1": (sc.TIER1, ["analysis_summary.json", "rq2/evaluate/*/pass_rates.json",
                         "rq2/evaluate/*/rankings.json", "rq4/degrade/*/degradation_analysis.json",
                         "rq4/augment/*/augment_analysis.json"]),
    "tier2_scores_v4": (sc.T2_SCORES, ["rq2/evaluate/*/pass_rates.json", "rq4/eligibility_tier2.json",
                                       "rq4/degrade/*/degradation_tier2.json",
                                       "rq4/augment/*/augment_tier2.json",
                                       "merge_provenance.json", "llm_conditions.json"]),
    "tier2_post_v5": (sc.T2_POST, ["rq2/evaluate/*/rankings*.json", "analysis_summary*.json",
                                   "rq4/summary/tier2_rq4.json"]),
}
PINNED = {  # files whose own hash is recorded (configs and corpora)
    "config/default.yaml": sc.REPO / "config" / "default.yaml",
    "config/tier2_realclasseval.yaml": sc.REPO / "config" / "tier2_realclasseval.yaml",
    "data/paraphrases/realclasseval_v1.json": sc.REPO / "data" / "paraphrases" / "realclasseval_v1.json",
    "data/realclasseval/source.json": sc.REPO / "data" / "realclasseval" / "source.json",
}

# Reference values from the Tier 1 / Tier 2 reports (tolerance 5e-4 on rounded figures).
REPORT = {
    "tier2_graded": {"control_mean": (0.817, 181), "llm_mean": (0.663, 188), "rev_llm": 0.135,
                     "rev_control": 0.072, "rev_n": 178, "rev_p": 1.43e-5, "strata": (217, 35, 123)},
    "tier2_pass1": {"control_mean": (0.822, 109), "llm_mean": (0.694, 115), "rev_llm": 0.112,
                    "rev_control": 0.072, "rev_n": 106, "rev_p": 0.0178, "strata": None},
    "tier1": {"control_mean": (0.847, 22), "llm_mean": (0.771, 24), "rev_llm": 0.126,
              "rev_control": 0.056, "rev_n": 27, "rev_p": 0.158, "strata": (34, 129, 1)},
}


def freeze() -> dict:
    manifest = {"git": sc.git_state(), "pinned_files": {k: (sc.sha256_file(p) if p.exists() else None)
                                                         for k, p in PINNED.items()}, "trees": {}}
    per_file = {}
    for name, (root, patterns) in TREES.items():
        t = sc.hash_tree(root, patterns)
        per_file[name] = t.pop("files")
        manifest["trees"][name] = t
    sc.dump(MANIFEST, manifest)
    sc.dump(FILE_HASHES, per_file)
    return manifest


def verify_unchanged() -> list[str]:
    """Re-hash every frozen tree and report any difference from the recorded manifest."""
    recorded = json.loads(MANIFEST.read_text())
    problems = []
    for name, (root, patterns) in TREES.items():
        now = sc.hash_tree(root, patterns)
        old = recorded["trees"][name]
        if now["tree_sha256"] != old["tree_sha256"] or now["n_files"] != old["n_files"]:
            problems.append(f"{name}: tree hash changed ({old['n_files']} -> {now['n_files']} files)")
    for k, p in PINNED.items():
        if recorded["pinned_files"].get(k) != (sc.sha256_file(p) if p.exists() else None):
            problems.append(f"{k}: file hash changed")
    return problems


def _rq2(ar, view: Path, rankings: str) -> dict:
    ar.RESULTS, ar.RANKINGS = view, rankings
    ar.EXCLUDE.clear()
    return ar.analyze_rq2()


def _row(label, expected, got, ok) -> dict:
    return {"item": label, "expected": expected, "reproduced": got, "ok": bool(ok)}


def reproduce(ar, views) -> list[dict]:
    rows = []
    runs = {"tier1": (views["tier1"], "tier1"), "tier2_graded": (views["tier2"], "tier2_graded"),
            "tier2_pass1": (views["tier2"], "tier2_pass1")}
    for name, (view, key) in runs.items():
        ranking, summary_path = sc.RANKING_RUNS[key]
        stored = json.loads(summary_path.read_text())
        # rankings_pass1 summary and the graded one both keep the RQ2 block under "rq2"
        got = _rq2(ar, view, ranking)
        worst, other = sc.deep_diff(stored["rq2"], got)
        rows.append(_row(f"{name}: full RQ2 block equals the stored analysis summary",
                         f"max |diff| <= 1e-9, 0 other mismatches",
                         f"max |diff| {worst:.1e}, {len(other)} other mismatches {other[:2]}",
                         worst <= 1e-9 and not other))
        ref = REPORT[key]
        arms = got["ranking_stability"]["by_arm"]
        ctl, llm = arms["control"], arms["llm"]
        rows.append(_row(f"{name}: control tau_b (report)", ref["control_mean"],
                         (round(ctl["mean"], 3), ctl["n"]),
                         abs(ctl["mean"] - ref["control_mean"][0]) < 5e-4 and ctl["n"] == ref["control_mean"][1]))
        rows.append(_row(f"{name}: paraphrase tau_b (report)", ref["llm_mean"],
                         (round(llm["mean"], 3), llm["n"]),
                         abs(llm["mean"] - ref["llm_mean"][0]) < 5e-4 and llm["n"] == ref["llm_mean"][1]))
        pv = got["pairwise_reversal_rate"]["arm_vs_control_paired"]["llm"]
        rows.append(_row(f"{name}: paired reversal llm vs control (report)",
                         (ref["rev_llm"], ref["rev_control"], ref["rev_n"], ref["rev_p"]),
                         (round(pv["mean_arm"], 3), round(pv["mean_control"], 3), pv["n_tasks"],
                          float(f"{pv['wilcoxon']['p_value']:.3g}")),
                         abs(pv["mean_arm"] - ref["rev_llm"]) < 5e-4 and abs(pv["mean_control"] - ref["rev_control"]) < 5e-4
                         and pv["n_tasks"] == ref["rev_n"] and abs(pv["wilcoxon"]["p_value"] / ref["rev_p"] - 1) < 5e-3))
        if ref["strata"]:
            s = got["task_strata"]
            rows.append(_row(f"{name}: task strata discriminating/saturated/floor", ref["strata"],
                             (s["discriminating"], s["saturated"], s["floor"]),
                             (s["discriminating"], s["saturated"], s["floor"]) == ref["strata"]))
    return rows


def reproduce_rq4(ar) -> list[dict]:
    from types import SimpleNamespace

    from meta_real_eval.core.config import Config
    from meta_real_eval.rq4 import tier2

    rows = []
    cfg = Config.from_yaml(sc.REPO / "config" / "tier2_realclasseval.yaml")
    cfg.project.output_dir = sc.T2_SCORES
    tasks = [SimpleNamespace(label=p.name) for p in sorted((sc.T2_SCORES / "rq4" / "degrade").iterdir()) if p.is_dir()]
    got = tier2.analyze_tier2(cfg, tasks)
    stored = json.loads((sc.T2_POST / "rq4" / "summary" / "tier2_rq4.json").read_text())
    worst, other = sc.deep_diff(stored, got)
    rows.append(_row("tier2 RQ4: analysis recomputed from the stored cells equals tier2_rq4.json",
                     "max |diff| <= 1e-9, 0 other mismatches",
                     f"max |diff| {worst:.1e}, {len(other)} other mismatches {other[:2]}", worst <= 1e-9 and not other))
    r = got["designs"]["units"]["mean_primary"]
    rows.append(_row("tier2 RQ4 (units, graded): collapse at 20/50/80% and Page's L z",
                     ({"0.2": 3, "0.5": 15, "0.8": 26}, -0.2141), (r["ranking_collapse"], r["h1b_pages_l"]["z"]),
                     r["ranking_collapse"] == {"0.2": 3, "0.5": 15, "0.8": 26} and abs(r["h1b_pages_l"]["z"] + 0.2141) < 5e-4))
    ar.RESULTS = sc.TIER1
    got1 = ar.analyze_rq4()
    stored1 = json.loads((sc.TIER1 / "analysis_summary.json").read_text())["rq4"]
    worst, other = sc.deep_diff(stored1, got1)
    rows.append(_row("tier1 RQ4: analysis equals the stored analysis summary", "max |diff| <= 1e-9, 0 other mismatches",
                     f"max |diff| {worst:.1e}, {len(other)} other mismatches {other[:2]}", worst <= 1e-9 and not other))
    q, p = got1["ranking_collapse"]["cochran_q"], got1["trend_test_h1b"]["p_value"]
    rows.append(_row("tier1 RQ4: Cochran Q and Page's L p (report)", (32.36, 0.775), (round(q, 2), round(p, 3)),
                     abs(q - 32.36) < 5e-3 and abs(p - 0.775) < 5e-4))
    return rows


def handling_checks(ar, views) -> list[dict]:
    """Missing values, exact ties and undefined correlations, counted on the stored files."""
    from meta_real_eval.rq2.ranking import cell_is_scored, comparable

    rows = []
    for tier, key_by in (("tier1", ["pass@1"]), ("tier2", ["mean_primary", "pass@1"])):
        view = views[tier] / "rq2" / "evaluate"
        for key in key_by:
            n_cells = n_unscored = near = merged = n_rel = n_undef = 0
            for td in sorted(p for p in view.iterdir() if p.is_dir()):
                pr = json.loads((td / "pass_rates.json").read_text())
                for rel, by_model in pr.items():
                    vals = []
                    for m, cell in by_model.items():
                        n_cells += 1
                        if cell_is_scored(cell, key):
                            vals.append(cell[key])
                        else:
                            n_unscored += 1
                    for i in range(len(vals)):
                        for j in range(i + 1, len(vals)):
                            if vals[i] != vals[j] and abs(vals[i] - vals[j]) < 1e-9:
                                near += 1
                                merged += comparable(vals[i]) == comparable(vals[j])
                rk = json.loads((td / ("rankings.json" if key == "mean_primary" or tier == "tier1" else "rankings_pass1.json")).read_text())
                n_rel += len(rk["tau_b_per_relation"])
                n_undef += sum(v is None for v in rk["tau_b_per_relation"].values())
            rows.append(_row(f"{tier}/{key}: raw float near-ties (differ < 1e-9 but not equal) merged by comparable()",
                             "all merged", f"{merged} of {near}", merged == near))
            rows.append({"item": f"{tier}/{key}: unscored cells (missing/incomplete/error) of {n_cells}; undefined tau_b "
                                 f"(task, relation) pairs of {n_rel}",
                         "expected": "reported, never imputed", "reproduced": f"{n_unscored} unscored; {n_undef} undefined",
                         "ok": True})
    return rows


def write_report(rows: list[dict], verify_problems: list[str], manifest: dict) -> None:
    lines = ["# Baseline verification (saturation analysis, Phase 1)", "",
             f"Git HEAD `{manifest['git']['head'][:10]}`; tags {manifest['git']['tags']}. "
             "Inputs are read-only; hashes are recorded in `results_saturation/baseline_manifest.json`.", "",
             "| Item | Expected | Reproduced | Status |", "|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['item']} | {r['expected']} | {r['reproduced']} | {'OK' if r['ok'] else '**FAIL**'} |")
    lines += ["", "## Frozen inputs", "", "| Tree | Files | Tree SHA-256 |", "|---|---|---|"]
    for name, t in manifest["trees"].items():
        lines.append(f"| {name} (`{t['root']}`) | {t['n_files']} | `{t['tree_sha256'][:16]}...` |")
    lines += ["", f"Re-hash after verification: {'**unchanged**' if not verify_problems else verify_problems}", ""]
    sc.DOC.mkdir(parents=True, exist_ok=True)
    (sc.DOC / "baseline_verification.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="only re-hash against the recorded freeze")
    args = ap.parse_args()
    if args.verify:
        problems = verify_unchanged()
        print("unchanged" if not problems else problems)
        return int(bool(problems))
    frozen_before = MANIFEST.exists()
    manifest = json.loads(MANIFEST.read_text()) if frozen_before else freeze()
    print("manifest:", MANIFEST, "(existing freeze reused)" if frozen_before else "(frozen now)")
    views = sc.build_views()
    ar = sc.load_analyze_results()
    rows = reproduce(ar, views) + reproduce_rq4(ar) + handling_checks(ar, views)
    problems = verify_unchanged()
    write_report(rows, problems, manifest)
    sc.dump(sc.OUT / "baseline_verification.json", {"rows": rows, "hash_problems": problems})
    bad = [r for r in rows if not r["ok"]]
    for r in rows:
        print(("OK   " if r["ok"] else "FAIL ") + r["item"], "->", r["reproduced"])
    print(f"\n{len(rows) - len(bad)}/{len(rows)} lines OK; inputs unchanged: {not problems}")
    return int(bool(bad or problems))


if __name__ == "__main__":
    sys.exit(main())
