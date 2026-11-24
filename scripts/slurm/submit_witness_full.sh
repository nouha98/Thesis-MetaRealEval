#!/bin/bash
# CPU array job: Stage 2 full witness run on the 351 evaluation tasks (plan rev. 9.3), after G2.
# Each array task processes labels[i::N]; finished tasks are skipped, so resubmitting resumes.
# No model is called.
#
# Usage (login node, repo root):
#   1. shards (needs the PASSED G2 record of the authoritative pilot):
#        sbatch --array=0-7 scripts/slurm/submit_witness_full.sh \
#            --g2 results_tier2_ext/witness/dev_pilot_freia/G2.json
#   2. merge + RQ1 robustness table, after every shard finished OK:
#        sbatch --dependency=afterok:<ARRAY_JOB_ID> scripts/slurm/submit_witness_full.sh --summarise
#
#SBATCH --job-name=witness_full
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=10:00:00
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --error=logs/slurm_%A_%a.err

set -euo pipefail

CONFIG="config/tier2_extensions.yaml"
OUT="results_tier2_ext/witness/full"
G2=""
SUMMARISE=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config) CONFIG="${2:?}"; shift 2 ;;
        --out) OUT="${2:?}"; shift 2 ;;
        --g2) G2="${2:?}"; shift 2 ;;
        --summarise) SUMMARISE=1; shift ;;
        *) echo "unknown argument $1" >&2; exit 2 ;;
    esac
done

export MRE_RUNNER_MODULE="meta_real_eval.stage0.runner"
export MRE_CONFIG="${CONFIG}"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

if [[ "${SUMMARISE}" == 1 ]]; then
    echo "Job ${SLURM_JOB_ID:-local}: merge witness shards in ${OUT}"
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/run_witness.py --config "${CONFIG}" --out "${OUT}" --summarise
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/analyze_rq1_witness.py --witness "${OUT}"
    exit 0
fi

[[ -n "${G2}" ]] || { echo "ERROR: --g2 <pilot>/G2.json is required for the full run" >&2; exit 2; }
SHARD="${SLURM_ARRAY_TASK_ID:-0}"
SHARDS="${SLURM_ARRAY_TASK_COUNT:-1}"
echo "Job ${SLURM_JOB_ID:-local} shard ${SHARD}/${SHARDS}: witness eval -> ${OUT}"
"${PY}" -c "import hypothesis; assert hypothesis.__version__ == '6.170.15', hypothesis.__version__"

srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/run_witness.py --config "${CONFIG}" --tasks eval \
    --g2 "${G2}" --out "${OUT}" --workers "${SLURM_CPUS_PER_TASK:-8}" --shard "${SHARD}" --shards "${SHARDS}"
