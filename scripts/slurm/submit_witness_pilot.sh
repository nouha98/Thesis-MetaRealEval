#!/bin/bash
# CPU job: authoritative Stage 2 development pilot + gate G2 (extensions plan rev. 9.3).
#   1. verify the frozen protocol artifacts against the gate manifest (freeze_protocol --check)
#   2. witness search on the 24 development tasks with the FROZEN reviewed contracts
#      (no re-drafting: contracts_v1/ is frozen; only reviewed contracts count)
#   3. RQ1 robustness summary (descriptive on the pilot)
#   4. gate G2 (fixtures, checks, independent replay of every witness) -> <out>/G2.json, G2.md
#
# Usage (login node, repo root):
#   sbatch scripts/slurm/submit_witness_pilot.sh
#   sbatch scripts/slurm/submit_witness_pilot.sh --out results_tier2_ext/witness/dev_pilot_freia
#
# No model is called. The job exits non-zero if G2 does not pass.
#
#SBATCH --job-name=witness_pilot
#SBATCH --cpus-per-task=16
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

CONFIG="config/tier2_extensions.yaml"
OUT="results_tier2_ext/witness/dev_pilot_freia"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config) CONFIG="${2:?--config needs a path}"; shift 2 ;;
        --out) OUT="${2:?--out needs a path}"; shift 2 ;;
        *) echo "unknown argument $1" >&2; exit 2 ;;
    esac
done

export MRE_RUNNER_MODULE="meta_real_eval.stage0.runner"
export MRE_CONFIG="${CONFIG}"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

echo "Job ${SLURM_JOB_ID}: Stage 2 development pilot -> ${OUT}"
"${PY}" -c "import hypothesis; assert hypothesis.__version__ == '6.170.15', hypothesis.__version__"

srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/freeze_protocol.py --config "${CONFIG}" --check
srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/run_witness.py --config "${CONFIG}" --tasks dev \
    --out "${OUT}" --workers "${SLURM_CPUS_PER_TASK:-8}"
srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/analyze_rq1_witness.py --witness "${OUT}"
srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/gate_g2.py --config "${CONFIG}" --pilot "${OUT}"
