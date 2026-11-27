"""Freeze canonical H v1 (plan D5, decisions 6-7): bundle, hashes, committed record.

    # 1. the section 7 decision (written after the A3 pilot; {"components": ["A2"]} when A3 does not join)
    #    -> config/extensions_protocol/canonical_h_decision.json
    # 2. freeze: copies every H-ready task's tests into the bundle and writes the committed record
    python scripts/freeze_h.py freeze --a2 results_tier2_ext/a2/full_v2 --audit results_tier2_ext/audit_h/round1 \
        --out results_tier2_ext/hidden_v1
    #    then commit config/extensions_protocol/hidden_v1_freeze.json and tag it: git tag tier2-hidden-v1
    # 3. check a bundle against the committed record (grade_hidden / eval_heldout do this under --after-freeze)
    python scripts/freeze_h.py verify --hidden results_tier2_ext/hidden_v1

Refuses to freeze unless the audit is accepted (estimates.json) and the section 7 decision exists. The bundle
is never overwritten. H outcomes on evaluation-cohort RQ2 completions are allowed only on a bundle that
verifies against the committed record.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ext_common as ec  # noqa: E402

from meta_real_eval.core.provenance import file_sha256, git_state  # noqa: E402

RECORD = ec.PROTOCOL_DIR / "hidden_v1_freeze.json"
# H v1.1 (decisions 10.8): a labelled post-hoc sensitivity with its own record; v1 stays primary
RECORDS = {"tier2-hidden-v1": RECORD, "tier2-hidden-v1.1": ec.PROTOCOL_DIR / "hidden_v1_1_freeze.json"}
SPECS = {"tier2-hidden-v1": "output_spec_v1.json", "tier2-hidden-v1.1": "output_spec_v1_1.json"}
DECISION = ec.PROTOCOL_DIR / "canonical_h_decision.json"
TASK_FILES = ("hidden_tests.py", "a2.json")


def bundle_hashes(hidden: Path) -> dict:
    """{task/file: sha256} for the test files of every task in the bundle."""
    return {f"{d.name}/{f}": file_sha256(d / f) for d in sorted(p for p in hidden.iterdir() if p.is_dir())
            for f in TASK_FILES if (d / f).is_file()}


def global_digest(files: dict) -> str:
    return hashlib.sha256("\n".join(f"{k}:{v}" for k, v in sorted(files.items())).encode()).hexdigest()


def freeze(a2: Path, audit: Path, out: Path, decision_path: Path = DECISION, record_path: Path = RECORD,
           version: str = "tier2-hidden-v1") -> dict:
    if out.exists():
        raise SystemExit(f"ERROR: {out} exists; a frozen bundle is never overwritten")
    if record_path.exists():
        raise SystemExit(f"ERROR: {record_path} exists: H v1 is already frozen")
    est = json.loads((audit / "estimates.json").read_text(encoding="utf-8"))
    if not est.get("acceptance", {}).get("accepted"):
        raise SystemExit("ERROR: the audit did not accept H (estimates.json); no freeze")
    if not decision_path.is_file():
        raise SystemExit(f"ERROR: {decision_path} missing: record the section 7 decision first")
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    if decision.get("components") != ["A2"]:
        raise SystemExit(f"ERROR: components {decision.get('components')}: only H = A2 is implemented; "
                         "merging A3 into the bundle is added together with A3")
    ready = sorted(d.name for d in a2.iterdir() if (d / "a2.json").is_file()
                   and json.loads((d / "a2.json").read_text(encoding="utf-8")).get("ready"))
    for lab in ready:
        (out / lab).mkdir(parents=True)
        for f in TASK_FILES:
            shutil.copy2(a2 / lab / f, out / lab / f)
    files = bundle_hashes(out)
    inputs = [ec.PROTOCOL_DIR / n for n in (SPECS[version], "cohorts_v1.json", "fault_split_v1.json",
                                            "contracts_v1/review_decisions.json")]
    inputs += [audit / "estimates.json", audit / "items.csv", audit / "audit_reserved.json", decision_path]
    record = {"version": version, "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "source": str(a2), "bundle": str(out), "components": decision["components"],
              "tasks": ready, "n_tasks": len(ready), "global_sha256": global_digest(files), "files": files,
              "inputs": {str(p.relative_to(ec.REPO)) if p.is_relative_to(ec.REPO) else str(p): file_sha256(p)
                         for p in inputs},
              "audit_acceptance": est["acceptance"], "grading": "one pytest process per hidden test (decisions 10.5)",
              "git": git_state()}
    text = json.dumps(record, indent=1)
    (out / "freeze_manifest.json").write_text(text, encoding="utf-8")
    record_path.write_text(text, encoding="utf-8")
    return record


def record_for(hidden: Path) -> Path:
    """The committed record of the H version the bundle's own manifest names."""
    man = hidden / "freeze_manifest.json"
    version = json.loads(man.read_text(encoding="utf-8"))["version"] if man.is_file() else "tier2-hidden-v1"
    if version not in RECORDS:
        raise SystemExit(f"ERROR: unknown H version {version!r} in {man}")
    return RECORDS[version]


def verify(hidden: Path, record_path: Path | None = None) -> dict:
    """The bundle must match the committed record file by file (no task added, removed or changed). Without
    ``record_path`` the record is chosen by the version the bundle's own manifest names."""
    if record_path is None:
        record_path = record_for(hidden)
    if not record_path.is_file():
        raise SystemExit(f"ERROR: {record_path} missing: H is not frozen")
    rec = json.loads(record_path.read_text(encoding="utf-8"))
    files = bundle_hashes(hidden)
    if files != rec["files"]:
        changed = sorted(k for k in set(files) | set(rec["files"]) if files.get(k) != rec["files"].get(k))
        raise SystemExit(f"ERROR: {hidden} differs from the frozen H ({len(changed)} file(s), e.g. {changed[:5]})")
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["freeze", "verify"])
    ap.add_argument("--a2", type=Path)
    ap.add_argument("--audit", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--hidden", type=Path)
    ap.add_argument("--version", choices=sorted(RECORDS), default="tier2-hidden-v1")
    args = ap.parse_args(argv)
    if args.cmd == "freeze":
        if not (args.a2 and args.audit and args.out):
            raise SystemExit("ERROR: freeze needs --a2, --audit and --out")
        rec = freeze(args.a2, args.audit, args.out, record_path=RECORDS[args.version], version=args.version)
        print(f"frozen {rec['n_tasks']} tasks, {len(rec['files'])} files, global sha256 {rec['global_sha256']}\n"
              f"-> {args.out}/freeze_manifest.json and {RECORDS[args.version]}; commit it, then: git tag {args.version}")
    else:
        if not args.hidden:
            raise SystemExit("ERROR: verify needs --hidden")
        rec = verify(args.hidden)
        print(f"OK: {args.hidden} matches {rec['version']} ({rec['n_tasks']} tasks, {rec['global_sha256'][:16]})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
