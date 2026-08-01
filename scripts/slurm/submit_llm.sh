#!/bin/bash
# LLM-bound single job: processes all tasks in one async process.
# Rate limiting (requests_per_minute in config) controls Innkube load.
#
# Usage: sbatch scripts/slurm/submit_llm.sh <stage> <phase>
# Example: sbatch scripts/slurm/submit_llm.sh rq2 generate
#
#SBATCH --job-name=submit_llm
#SBATCH --cpus-per-task=2
#SBATCH --time=24:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

STAGE=${1:?Usage: submit_llm.sh <stage> <phase>}
PHASE=${2:?Usage: submit_llm.sh <stage> <phase>}

export MRE_RUNNER_MODULE="meta_real_eval.${STAGE}.runner"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

echo "Job ${SLURM_JOB_ID}: ${STAGE} --phase ${PHASE} (LLM-bound, all tasks)"

srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" -m meta_real_eval.${STAGE}.runner \
    --config config/default.yaml \
    --phase "${PHASE}"
