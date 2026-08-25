#!/usr/bin/env python
"""Gate C: a review sheet for manual spot-checking of the paraphrase corpus.

Gates A (structural) and B (held-out judge) run inside the generator. Neither
can certify that a variant *reads* as the same task to a human, which is the
claim RQ2 rests on. This script draws a stratified random sample, balanced
across families, and writes it as a markdown sheet to review by hand. The
reviewed acceptance rate is a validity statistic for the write-up — it is not a
code gate and nothing here modifies the corpus.

It also prints the rejection breakdown from generation, which says how much work
the automatic gates did and where the generator model tends to fail.

    .venv/bin/python scripts/paraphrase_report.py
    .venv/bin/python scripts/paraphrase_report.py --n 50 --seed 42
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from meta_real_eval.rq2.corpus import load_corpus, tasks_sha256  # noqa: E402

DEFAULT_CORPUS = REPO_ROOT / "data" / "paraphrases" / "humaneval_v1.json"


def sample_variants(corpus: dict, n: int, seed: int) -> list[dict]:
    """Draw ~n variants, spread as evenly as possible over families.

    Balanced rather than uniform: a family that generated fewer variants is
    exactly the one whose quality is least certain, so proportional sampling
    would under-review it.
    """
    by_family: dict[str, list[dict]] = defaultdict(list)
    for task_id, entry in corpus["tasks"].items():
        for variant in entry["variants"]:
            by_family[variant["family"]].append(
                {"task_id": task_id, "original": entry["original"], **variant}
            )

    rng = random.Random(seed)
    families = sorted(by_family)
    per_family = max(1, n // max(len(families), 1))
    sampled: list[dict] = []
    for family in families:
        pool = by_family[family]
        sampled.extend(rng.sample(pool, min(per_family, len(pool))))
    rng.shuffle(sampled)
    return sampled


def rejection_stats(corpus_dir: Path) -> dict:
    path = corpus_dir / "generation_rejections.json"
    if not path.exists():
        return {}
    rejections = json.loads(path.read_text(encoding="utf-8"))
    by_gate = Counter(r.get("gate", "?") for r in rejections)
    by_reason = Counter(r.get("reason", "?").split(":")[0] for r in rejections)
    by_family = Counter(r.get("family", "?") for r in rejections)
    return {"total": len(rejections), "by_gate": dict(by_gate),
            "by_reason": dict(by_reason.most_common()), "by_family": dict(by_family)}


def write_sheet(sampled: list[dict], corpus: dict, out: Path) -> None:
    manifest = corpus["manifest"]
    lines = [
        "# Paraphrase corpus review sheet (Gate C)",
        "",
        f"- corpus version: `{manifest.get('corpus_version')}`",
        f"- generator: `{manifest.get('generator_model')}` · "
        f"judge: `{manifest.get('judge_model')}`",
        f"- sha256: `{manifest.get('sha256')}`",
        f"- sample: {len(sampled)} variants",
        "",
        "For each item, mark **equivalent** or **not equivalent**: does the rewrite "
        "demand exactly the same function as the original? Wording, tone and the "
        "order of requirements are not differences in meaning.",
        "",
        "| # | verdict (fill in) | note |",
        "|---|---|---|",
    ]
    lines += [f"| {i} |  |  |" for i in range(1, len(sampled) + 1)]
    lines.append("")

    for i, variant in enumerate(sampled, start=1):
        lines += [
            "---",
            "",
            f"## {i}. {variant['task_id']} — `{variant['variant_id']}` "
            f"({variant['family']})",
            "",
            "**Original**",
            "",
            "```python",
            variant["original"].rstrip("\n"),
            "```",
            "",
            "**Rewrite**",
            "",
            "```python",
            variant["text"].rstrip("\n"),
            "```",
            "",
            f"_judge: {variant['validation'].get('judge_verdict')} — "
            f"{variant['validation'].get('judge_reason', '')}_",
            "",
        ]

    out.write_text("\n".join(lines), encoding="utf-8")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Paraphrase corpus review sheet")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--n", type=int, default=50)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    corpus = load_corpus(args.corpus)
    out = args.out or args.corpus.parent / "review_sheet.md"

    n_variants = sum(len(t["variants"]) for t in corpus["tasks"].values())
    families = corpus["manifest"].get("families", [])
    n_per_family = corpus["manifest"].get("n_per_family", 0)
    expected = len(corpus["tasks"]) * len(families) * n_per_family

    print(f"corpus      : {args.corpus}")
    print(f"sha256      : {tasks_sha256(corpus)}")
    print(f"tasks       : {len(corpus['tasks'])}")
    pct = f" ({100 * n_variants / expected:.1f}%)" if expected else ""
    print(f"variants    : {n_variants}/{expected} slots filled{pct}")

    by_family = Counter(v["family"] for t in corpus["tasks"].values()
                        for v in t["variants"])
    print("\nfilled by family:")
    for family in families:
        cap = len(corpus["tasks"]) * n_per_family
        print(f"  {family:10s} {by_family[family]:5d}/{cap}")

    attempts = Counter(v["validation"].get("n_regen_attempts", 1)
                       for t in corpus["tasks"].values() for v in t["variants"])
    print("\naccepted on attempt:")
    for attempt in sorted(attempts):
        print(f"  attempt {attempt}: {attempts[attempt]}")

    stats = rejection_stats(args.corpus.parent)
    if stats:
        print(f"\nrejections  : {stats['total']}")
        print(f"  by gate   : {stats['by_gate']}")
        print(f"  by reason : {stats['by_reason']}")
        print(f"  by family : {stats['by_family']}")

    gaps_path = args.corpus.parent / "generation_gaps.json"
    if gaps_path.exists():
        gaps = json.loads(gaps_path.read_text(encoding="utf-8"))
        print(f"\ngaps        : {len(gaps)} (task, family) slot group(s) unfilled")

    sampled = sample_variants(corpus, args.n, args.seed)
    write_sheet(sampled, corpus, out)
    print(f"\nWrote review sheet: {out} ({len(sampled)} variants)")


if __name__ == "__main__":
    main()
