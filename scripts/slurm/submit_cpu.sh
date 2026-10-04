#!/bin/bash
# CPU-bound job array: one benchmark task per SLURM_ARRAY_TASK_ID.
#
# Usage:
#   sbatch --array=0-163 scripts/slurm/submit_cpu.sh stage0
#   sbatch --array=0-163 scripts/slurm/submit_cpu.sh rq2 evaluate
#   sbatch --array=0-163 scripts/slurm/submit_cpu.sh rq2 evaluate --force
#   sbatch --array=0-N   scripts/slurm/submit_cpu.sh stage0 --config config/tier2_realclasseval.yaml
#
# --config defaults to config/default.yaml (Tier 1); the array range itself is
# NOT derived here -- it's sized by the caller (see submit_pipeline.sh, which
# uses `python -m meta_real_eval.benchmarks count --config ...`).
#
#SBATCH --job-name=submit_cpu
#SBATCH --cpus-per-task=4
#SBATCH --mem=4G
#SBATCH --time=00:30:00
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --error=logs/slurm_%A_%a.err

set -euo pipefail

STAGE=${1:?Usage: submit_cpu.sh <stage> [phase] [--config path] [--force]}
shift

PHASE=""
CONFIG="config/default.yaml"
FORCE_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force) FORCE_ARGS=(--force); shift ;;
        --config) CONFIG="${2:?--config needs a path}"; shift 2 ;;
        *) PHASE="$1"; shift ;;
    esac
done

export MRE_RUNNER_MODULE="meta_real_eval.${STAGE}.runner"
export MRE_CONFIG="${CONFIG}"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

TASK_INDEX="${SLURM_ARRAY_TASK_ID:-0}"

if [[ "${STAGE}" == "stage0" ]]; then
    echo "Job ${SLURM_JOB_ID} array-task ${TASK_INDEX}: stage0${FORCE_ARGS:+ (forced)}"
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" -m meta_real_eval.stage0.runner \
        --config "${CONFIG}" \
        --task-index "${TASK_INDEX}" \
        ${FORCE_ARGS[@]+"${FORCE_ARGS[@]}"}
elif [[ -n "${PHASE}" ]]; then
    echo "Job ${SLURM_JOB_ID} array-task ${TASK_INDEX}: ${STAGE} --phase ${PHASE}${FORCE_ARGS:+ (forced)}"
    srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" -m meta_real_eval.${STAGE}.runner \
        --config "${CONFIG}" \
        --phase "${PHASE}" \
        --task-index "${TASK_INDEX}" \
        ${FORCE_ARGS[@]+"${FORCE_ARGS[@]}"}
else
    echo "ERROR: phase required for stage '${STAGE}'" >&2
    exit 1
fi
