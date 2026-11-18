#!/bin/bash
# CPU array job: Stage 2b coupling detection matrices (protocol_freeze_decisions.md section 9).
# No model is called. Each array task processes labels[i::N] and skips tasks already done.
#
# Usage (login node, repo root):
#   technical pilot (development tasks, one job):
#     sbatch --array=0-0 scripts/slurm/submit_coupling.sh --tasks dev --out results_tier2_ext/coupling/dev_pilot_freia
#   full run (after freeze_coupling.py; e.g. 25 shards):
#     sbatch --array=0-24 scripts/slurm/submit_coupling.sh --tasks all --out results_tier2_ext/coupling/full
#
#SBATCH --job-name=coupling
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=12:00:00
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --error=logs/slurm_%A_%a.err

set -euo pipefail

CONFIG="config/tier2_extensions.yaml"
OUT="results_tier2_ext/coupling/full"
TASKS="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config) CONFIG="${2:?}"; shift 2 ;;
        --out) OUT="${2:?}"; shift 2 ;;
        --tasks) TASKS="${2:?}"; shift 2 ;;
        *) echo "unknown argument $1" >&2; exit 2 ;;
    esac
done

export MRE_RUNNER_MODULE="meta_real_eval.stage0.runner"
export MRE_CONFIG="${CONFIG}"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

SHARD="${SLURM_ARRAY_TASK_ID:-0}"
SHARDS="${SLURM_ARRAY_TASK_COUNT:-1}"
echo "Job ${SLURM_JOB_ID:-local} shard ${SHARD}/${SHARDS}: coupling ${TASKS} -> ${OUT}"
"${PY}" -c "import hypothesis; assert hypothesis.__version__ == '6.170.15', hypothesis.__version__"

srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/run_coupling.py --config "${CONFIG}" --tasks ${TASKS} \
    --out "${OUT}" --workers "${SLURM_CPUS_PER_TASK:-8}" --shard "${SHARD}" --shards "${SHARDS}"
