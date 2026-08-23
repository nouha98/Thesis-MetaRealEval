#!/bin/bash
# Full pipeline submission with SLURM dependency chains.
#
# CPU-bound phases → job arrays (one task per array element).
# LLM-bound phases → single jobs (all tasks, async, rate-limited).
#
# IMPORTANT: set benchmark.tasks in config/default.yaml BEFORE submitting:
#   tasks: null        → full HumanEval (164 tasks, indices 0..163)
#   tasks: [0, 1, 10]   → only those tasks (for LLM generate phases)
#
# Usage:
#   bash scripts/slurm/submit_pipeline.sh           # array 0..163
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

N_TASKS=163   # 164 tasks: HumanEval indices 0..163
FORCE=""
ALLOW_UNCALIBRATED=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --tasks) N_TASKS=$(($2 - 1)); shift 2 ;;
        --force) FORCE="--force"; shift ;;
        --allow-uncalibrated) ALLOW_UNCALIBRATED=1; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

ARRAY_RANGE="0-${N_TASKS}"
CPU_SCRIPT="scripts/slurm/submit_cpu.sh"
CPU_SINGLE="scripts/slurm/submit_cpu_single.sh"
LLM_SCRIPT="scripts/slurm/submit_llm.sh"

mkdir -p logs results cache data

# Pre-stage the HumanEval corpus while we are still on the login node —
# compute nodes have no outbound internet. No-op if already fetched.
.venv/bin/python scripts/fetch_data.py

# --- calibration preflight -------------------------------------------------
# rq3.divergence_threshold decides which tasks receive MT consistency assertions.
# Left null it silently falls back to 0.1, so a full run would produce RQ4 numbers
# gated on an arbitrary constant. The Tier-1 pilot is what calibrates it, so that
# run passes --allow-uncalibrated; every later run must not need to.
THRESHOLD=$(sed -n 's/^[[:space:]]*divergence_threshold:[[:space:]]*\([^#]*\).*/\1/p' \
            config/default.yaml | head -1 | tr -d '[:space:]')

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

echo "Submitting Meta-Real-Eval pipeline for task indices 0..${N_TASKS}"
echo "Config: config/default.yaml"
echo ""

S0=$(sbatch --parsable --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" stage0 ${FORCE})
echo "Stage 0:          job ${S0}  (array ${ARRAY_RANGE})"

RQ1G=$(sbatch --parsable --dependency=afterok:"${S0}" "${LLM_SCRIPT}" rq1 generate ${FORCE})
echo "RQ1 generate:     job ${RQ1G}  (single, LLM-bound)"

RQ1E=$(sbatch --parsable --dependency=afterok:"${RQ1G}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq1 evaluate ${FORCE})
echo "RQ1 evaluate:     job ${RQ1E}  (array ${ARRAY_RANGE})"

# RQ2 depends on Stage 0 only, NOT on RQ1. Nothing in RQ2/RQ3/RQ4 reads any
# results/rq1/* artifact - RQ1 asks whether the *test suite* is adequate, while
# RQ2-RQ4 ask whether *model rankings* are stable. Chaining them meant an RQ1
# crash burned the 24h RQ2 generate budget for no scientific reason. The two
# branches are joined once, at analysis time, in scripts/analyze_results.py.
RQ2G=$(sbatch --parsable --dependency=afterok:"${S0}" "${LLM_SCRIPT}" rq2 generate ${FORCE})
echo "RQ2 generate:     job ${RQ2G}  (single, LLM-bound, parallel with RQ1) *** main bottleneck ***"

RQ2E=$(sbatch --parsable --dependency=afterok:"${RQ2G}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq2 evaluate ${FORCE})
echo "RQ2 evaluate:     job ${RQ2E}  (array ${ARRAY_RANGE})"

RQ3X=$(sbatch --parsable --dependency=afterok:"${RQ2E}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq3 execute ${FORCE})
echo "RQ3 execute:      job ${RQ3X}  (array ${ARRAY_RANGE})"

RQ3S=$(sbatch --parsable --dependency=afterok:"${RQ3X}" "${LLM_SCRIPT}" rq3 score ${FORCE})
echo "RQ3 score:        job ${RQ3S}  (single, LLM-bound)"

# RQ4 needs RQ3's *divergence* (RQ3X), not its SBC scores: sbc_scores.json is
# written by RQ3 score and read by nothing. Depending on RQ3S meant a failure in
# that LLM-bound job blocked all of RQ4 for no data reason. RQ3S still runs, now
# in parallel with RQ4.
RQ4D=$(sbatch --parsable --dependency=afterok:"${RQ3X}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq4 degrade ${FORCE})
echo "RQ4 degrade:      job ${RQ4D}  (array ${ARRAY_RANGE}, parallel with RQ3 score)"

RQ4A=$(sbatch --parsable --dependency=afterok:"${RQ4D}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq4 augment ${FORCE})
echo "RQ4 augment:      job ${RQ4A}  (array ${ARRAY_RANGE})"

# Waits on RQ1 as well: the cross-RQ join in scripts/analyze_results.py needs
# RQ1b's per-task oracle-adequacy covariate to be on disk.
RQ4Z=$(sbatch --parsable --dependency=afterok:"${RQ4A}":"${RQ1E}" "${CPU_SINGLE}" rq4 analyze)
echo "RQ4 analyze:      job ${RQ4Z}  (single, CPU-bound; waits on RQ4A + RQ1E)"

echo ""
echo "Pipeline submitted. Final job ID: ${RQ4Z}"
echo "Monitor:  squeue -u \$USER"
echo "Progress: python scripts/progress.py --config config/default.yaml"
