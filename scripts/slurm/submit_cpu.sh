#!/bin/bash
# CPU-bound job array: one HumanEval task per SLURM_ARRAY_TASK_ID.
#
# Usage:
#   sbatch --array=0-163 scripts/slurm/submit_cpu.sh stage0
#   sbatch --array=0-163 scripts/slurm/submit_cpu.sh rq2 evaluate
#
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --output=logs/slurm_%A_%a.out
#SBATCH --error=logs/slurm_%A_%a.err

set -euo pipefail

STAGE=${1:?Usage: submit_cpu.sh <stage> [phase]}
PHASE=${2:-}

cd "${SLURM_SUBMIT_DIR}"
PY=.venv/bin/python

if [[ "${STAGE}" == "stage0" ]]; then
    echo "Job ${SLURM_JOB_ID} array-task ${SLURM_ARRAY_TASK_ID}: stage0"
    "${PY}" -m meta_real_eval.stage0.runner \
        --config config/default.yaml \
        --task-index "${SLURM_ARRAY_TASK_ID}"
elif [[ -n "${PHASE}" ]]; then
    echo "Job ${SLURM_JOB_ID} array-task ${SLURM_ARRAY_TASK_ID}: ${STAGE} --phase ${PHASE}"
    "${PY}" -m meta_real_eval.${STAGE}.runner \
        --config config/default.yaml \
        --phase "${PHASE}" \
        --task-index "${SLURM_ARRAY_TASK_ID}"
else
    echo "ERROR: phase required for stage '${STAGE}'" >&2
    exit 1
fi
