#!/bin/bash
# CPU-bound single job (no array). Used for cross-task aggregation steps.
#
# Usage:
#   sbatch scripts/slurm/submit_cpu_single.sh rq4 analyze
#
#SBATCH --job-name=submit_cpu_single
#SBATCH --cpus-per-task=2
#SBATCH --time=01:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

STAGE=${1:?Usage: submit_cpu_single.sh <stage> <phase>}
PHASE=${2:?Usage: submit_cpu_single.sh <stage> <phase>}

export MRE_RUNNER_MODULE="meta_real_eval.${STAGE}.runner"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

echo "Job ${SLURM_JOB_ID}: ${STAGE} --phase ${PHASE} (CPU single job)"

srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" -m meta_real_eval.${STAGE}.runner \
    --config config/default.yaml \
    --phase "${PHASE}"
