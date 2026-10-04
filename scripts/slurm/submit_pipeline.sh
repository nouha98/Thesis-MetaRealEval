#!/bin/bash
# Full pipeline submission with SLURM dependency chains.
#
# CPU-bound phases → job arrays (one task per array element).
# LLM-bound phases → single jobs (all tasks, async, rate-limited).
#
# IMPORTANT: set benchmark.tasks in the config BEFORE submitting:
#   tasks: null        → every task the benchmark exposes
#   tasks: [0, 1, 10]   → only those tasks (for LLM generate phases)
#
# Usage:
#   bash scripts/slurm/submit_pipeline.sh                    # full corpus, Tier 1 (default.yaml)
#   bash scripts/slurm/submit_pipeline.sh --config config/tier2_realclasseval.yaml
#                                                    # Tier 2 (needs the M0 gate already run:
#                                                    #   scripts/slurm/submit_m0_gate.sh)
#   bash scripts/slurm/submit_pipeline.sh --tasks 4 # array 0..3 (pilot)
#   bash scripts/slurm/submit_pipeline.sh --tasks 20 --allow-uncalibrated
#                                                    # Tier-1 pilot: rq3.divergence_threshold
#                                                    # is still null and this run is what
#                                                    # calibrates it. Afterwards:
#                                                    #   .venv/bin/python scripts/analyze_results.py --calibrate
#                                                    # then re-submit without the flag.
#   bash scripts/slurm/submit_pipeline.sh --force   # redo every stage from
#                                                    # scratch (ignores existing
#                                                    # _done.marker files). Back
#                                                    # up results/ first if you
#                                                    # want to keep the old run:
#                                                    #   ssh -l USER host "cd DIR && tar czf - results logs" > backup.tar.gz

set -euo pipefail

CONFIG="config/default.yaml"
N_TASKS=""        # unset → sized from the benchmark itself, below
FORCE=""
ALLOW_UNCALIBRATED=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --config) CONFIG="${2:?--config needs a path}"; shift 2 ;;
        --tasks) N_TASKS=$(($2 - 1)); shift 2 ;;
        --force) FORCE="--force"; shift ;;
        --allow-uncalibrated) ALLOW_UNCALIBRATED=1; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

CPU_SCRIPT="scripts/slurm/submit_cpu.sh"
CPU_SINGLE="scripts/slurm/submit_cpu_single.sh"
LLM_SCRIPT="scripts/slurm/submit_llm.sh"

mkdir -p logs results cache data

# Size the job array from the benchmark's own task count instead of a
# hard-coded constant -- HumanEval is 164 tasks (0..163), but RealClassEval's
# count depends on the M0 gate's manifest (which splits/docstring_variant are
# configured, and how many tasks the validity gate kept).
if [[ -z "${N_TASKS}" ]]; then
    N_TOTAL=$(.venv/bin/python -m meta_real_eval.benchmarks count --config "${CONFIG}")
    N_TASKS=$((N_TOTAL - 1))
fi
ARRAY_RANGE="0-${N_TASKS}"

BENCH_NAME=$(.venv/bin/python - "${CONFIG}" <<'PY'
import sys
sys.path.insert(0, "src")
from meta_real_eval.core.config import Config
print(Config.from_yaml(sys.argv[1]).benchmark.name)
PY
)

if [[ "${BENCH_NAME}" == "humaneval" ]]; then
    # Pre-stage the HumanEval corpus while we are still on the login node —
    # compute nodes have no outbound internet. No-op if already fetched.
    .venv/bin/python scripts/fetch_data.py
else
    # Tier 2's dataset + manifest are pre-staged by the M0 gate
    # (scripts/slurm/submit_m0_gate.sh), not here; _common.sh's own preflight
    # (run inside every job below) fails loudly if that hasn't happened yet.
    echo "benchmark: ${BENCH_NAME} — assuming its corpus/manifest is already staged (M0 gate)."
fi

# --- calibration preflight -------------------------------------------------
# rq3.divergence_threshold decides which tasks receive MT consistency assertions.
# Left null it silently falls back to 0.1, so a full run would produce RQ4 numbers
# gated on an arbitrary constant. The Tier-1 pilot is what calibrates it, so that
# run passes --allow-uncalibrated; every later run must not need to.
THRESHOLD=$(sed -n 's/^[[:space:]]*divergence_threshold:[[:space:]]*\([^#]*\).*/\1/p' \
            "${CONFIG}" | head -1 | tr -d '[:space:]')

if [[ -z "${THRESHOLD}" || "${THRESHOLD}" == "null" || "${THRESHOLD}" == "~" ]]; then
    if [[ -z "${ALLOW_UNCALIBRATED}" ]]; then
        echo "ERROR: rq3.divergence_threshold is not calibrated (currently null)." >&2
        echo "" >&2
        echo "  RQ4 would gate MT augmentation on a hardcoded 0.1 fallback and tag" >&2
        echo "  every result threshold_calibrated=false." >&2
        echo "" >&2
        echo "  Run the Tier-1 pilot first:" >&2
        echo "    bash scripts/slurm/submit_pipeline.sh --tasks 20 --allow-uncalibrated" >&2
        echo "  then calibrate from it:" >&2
        echo "    .venv/bin/python scripts/analyze_results.py --calibrate" >&2
        echo "  and re-submit this command." >&2
        exit 1
    fi
    echo "WARNING: rq3.divergence_threshold is null — running UNCALIBRATED."
    echo "         Every RQ4 result will be tagged threshold_calibrated=false."
    echo "         Calibrate afterwards with: scripts/analyze_results.py --calibrate"
    echo ""
else
    echo "tau_div (rq3.divergence_threshold): ${THRESHOLD}  [calibrated]"
    echo ""
fi

# The paraphrase corpus is an input to RQ2 generate, the 24h bottleneck job.
# Verifying it here means a missing file or a drifted hash fails in a second on
# the login node instead of after the queue wait. Same abort-don't-regenerate
# rule as the runtime check in rq2/generator.py.
if ! .venv/bin/python - "${CONFIG}" <<'PY'
import sys
sys.path.insert(0, "src")
from meta_real_eval.core.config import Config
from meta_real_eval.rq2.corpus import CorpusError, load_corpus, verify_corpus

cfg = Config.from_yaml(sys.argv[1])
path = cfg.rq2.paraphrase_corpus
if path is None:
    print("Paraphrase corpus: not configured — template arm only.")
    sys.exit(0)
try:
    corpus = load_corpus(path)
    verify_corpus(corpus, cfg.rq2.corpus_sha256, path)
except CorpusError as exc:
    print(f"ERROR: {exc}", file=sys.stderr)
    sys.exit(1)
filled = sum(len(t["variants"]) for t in corpus["tasks"].values())
print(f"Paraphrase corpus: {path}  [{len(corpus['tasks'])} tasks, "
      f"{filled} variants, sha256 verified]")
PY
then
    echo "" >&2
    echo "  Build or restore the corpus before submitting:" >&2
    echo "    .venv/bin/python scripts/generate_paraphrases.py" >&2
    echo "  then pin the sha256 it prints in rq2.corpus_sha256." >&2
    exit 1
fi
echo ""

echo "Submitting Meta-Real-Eval pipeline for task indices 0..${N_TASKS}"
echo "Config: ${CONFIG}"
echo ""

S0=$(sbatch --parsable --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" stage0 ${FORCE} --config "${CONFIG}")
echo "Stage 0:          job ${S0}  (array ${ARRAY_RANGE})"

RQ1G=$(sbatch --parsable --dependency=afterok:"${S0}" "${LLM_SCRIPT}" rq1 generate --config "${CONFIG}" ${FORCE})
echo "RQ1 generate:     job ${RQ1G}  (single, LLM-bound)"

RQ1E=$(sbatch --parsable --dependency=afterok:"${RQ1G}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq1 evaluate ${FORCE} --config "${CONFIG}")
echo "RQ1 evaluate:     job ${RQ1E}  (array ${ARRAY_RANGE})"

# RQ2 depends on Stage 0 only, NOT on RQ1. Nothing in RQ2/RQ3/RQ4 reads any
# results/rq1/* artifact - RQ1 asks whether the *test suite* is adequate, while
# RQ2-RQ4 ask whether *model rankings* are stable. Chaining them meant an RQ1
# crash burned the 24h RQ2 generate budget for no scientific reason. The two
# branches are joined once, at analysis time, in scripts/analyze_results.py.
RQ2G=$(sbatch --parsable --dependency=afterok:"${S0}" "${LLM_SCRIPT}" rq2 generate --config "${CONFIG}" ${FORCE})
echo "RQ2 generate:     job ${RQ2G}  (single, LLM-bound, parallel with RQ1) *** main bottleneck ***"

RQ2E=$(sbatch --parsable --dependency=afterok:"${RQ2G}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq2 evaluate ${FORCE} --config "${CONFIG}")
echo "RQ2 evaluate:     job ${RQ2E}  (array ${ARRAY_RANGE})"

RQ3X=$(sbatch --parsable --dependency=afterok:"${RQ2E}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq3 execute ${FORCE} --config "${CONFIG}")
echo "RQ3 execute:      job ${RQ3X}  (array ${ARRAY_RANGE})"

RQ3S=$(sbatch --parsable --dependency=afterok:"${RQ3X}" "${LLM_SCRIPT}" rq3 score --config "${CONFIG}" ${FORCE})
echo "RQ3 score:        job ${RQ3S}  (single, LLM-bound)"

# RQ4 needs RQ3's *divergence* (RQ3X), not its SBC scores: sbc_scores.json is
# written by RQ3 score and read by nothing. Depending on RQ3S meant a failure in
# that LLM-bound job blocked all of RQ4 for no data reason. RQ3S still runs, now
# in parallel with RQ4.
RQ4D=$(sbatch --parsable --dependency=afterok:"${RQ3X}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq4 degrade ${FORCE} --config "${CONFIG}")
echo "RQ4 degrade:      job ${RQ4D}  (array ${ARRAY_RANGE}, parallel with RQ3 score)"

RQ4A=$(sbatch --parsable --dependency=afterok:"${RQ4D}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq4 augment ${FORCE} --config "${CONFIG}")
echo "RQ4 augment:      job ${RQ4A}  (array ${ARRAY_RANGE})"

# Waits on RQ1 as well: the cross-RQ join in scripts/analyze_results.py needs
# RQ1b's per-task oracle-adequacy covariate to be on disk.
RQ4Z=$(sbatch --parsable --dependency=afterok:"${RQ4A}":"${RQ1E}" "${CPU_SINGLE}" rq4 analyze --config "${CONFIG}")
echo "RQ4 analyze:      job ${RQ4Z}  (single, CPU-bound; waits on RQ4A + RQ1E)"

echo ""
echo "Pipeline submitted. Final job ID: ${RQ4Z}"
echo "Monitor:  squeue -u \$USER"
echo "Progress: python scripts/progress.py --config ${CONFIG}"
