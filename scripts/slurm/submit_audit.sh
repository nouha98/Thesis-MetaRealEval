#!/bin/bash
# CPU-bound single job: verify Stage 0 / RQ1 results (scripts/audit_rq1.py).
# Not part of the <stage>.runner --phase pipeline, so this forwards its own flags
# directly instead of taking <stage> <phase> like submit_cpu_single.sh.
#
# Usage:
#   sbatch scripts/slurm/submit_audit.sh                       # all 164 tasks
#   sbatch --dependency=afterok:<rq1_evaluate_job_id> scripts/slurm/submit_audit.sh
#   sbatch scripts/slurm/submit_audit.sh --tasks 38 50 61 119   # just the known-fixed tasks
#
# Re-executes every recorded kill verdict and every equivalence exclusion, so
# it needs Stage 0 and RQ1 evaluate to have already run -- point it at that
# job with --dependency=afterok as shown above, or run it by hand once that
# job has finished. Exits non-zero (visible as job state FAILED) if it finds
# a verdict mismatch or an equivalence contradiction.
#
#SBATCH --job-name=submit_audit
#SBATCH --cpus-per-task=4
#SBATCH --time=00:30:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

# Not a <stage>.runner module, but audit_rq1.py imports rq1.runner's siblings
# directly, so checking that import still gets the same "fail fast with a
# readable message" preflight the other scripts get.
export MRE_RUNNER_MODULE="meta_real_eval.rq1.runner"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

echo "Job ${SLURM_JOB_ID}: audit Stage 0 / RQ1 results"

srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/audit_rq1.py \
    --config config/default.yaml \
    "$@"
