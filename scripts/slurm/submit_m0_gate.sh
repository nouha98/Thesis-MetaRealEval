#!/bin/bash
# Tier 2 M0: the authoritative RealClassEval validity gate.
#
# Two steps, in order, and the second only runs if the first passes:
#
#   1. The D6 fork-mode tests (tests/test_benchmarks/test_forkserver.py).
#      They are skipped on Windows, so this is the first place fork mode --
#      the production scenario mode -- is exercised at all. If fork and
#      fresh-process traces differ, STOP: the gate would be measuring with an
#      unvalidated instrument.
#   2. scripts/validate_realclasseval.py under --require-python 3.11, writing
#      data/realclasseval/manifest_v1.json + gate_report.md.
#
# Prerequisites, once, on the login node (internet):
#   .venv/bin/python scripts/fetch_realclasseval.py
#   .venv/bin/python scripts/scan_realclasseval_deps.py
#   .venv/bin/pip install -r requirements-tier2.in
#   .venv/bin/pip freeze > requirements-tier2.lock.txt   # commit this pin
# and the venv must be Python 3.11 (the version Pynguin generated the suites under).
#
# Usage:
#   sbatch scripts/slurm/submit_m0_gate.sh
#   sbatch scripts/slurm/submit_m0_gate.sh --force        # ignore per-task checkpoints
#   sbatch scripts/slurm/submit_m0_gate.sh --config config/tier2_realclasseval_v2.yaml
#
#SBATCH --job-name=m0_gate
#SBATCH --cpus-per-task=16
#SBATCH --time=04:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

# validate_realclasseval.py takes its own --config too; pulled out here so
# _common.sh's preflight loads the SAME config (and, where it names a split
# of the manifest other than the default, the same one the gate will write).
CONFIG="config/tier2_realclasseval.yaml"
ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --config) CONFIG="${2:?--config needs a path}"; shift 2 ;;
        *) ARGS+=("$1"); shift ;;
    esac
done

export MRE_RUNNER_MODULE="meta_real_eval.benchmarks.validate"
export MRE_CONFIG="${CONFIG}"
# This job BUILDS data/realclasseval/manifest_v1.json; _common.sh's generic
# dataset preflight calls load_tasks(), which requires that manifest to
# already exist -- true for every other job, backwards for this one.
export MRE_SKIP_DATASET_CHECK=1
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

echo "Job ${SLURM_JOB_ID}: M0 gate -- step 1/2: D6 fork-mode tests"
# A skipped fork test still exits 0, so require fork explicitly: the point of
# this step is that the fork tests actually RUN.
"${PY}" -c "import os, sys; sys.exit(0 if hasattr(os, 'fork') else 'ERROR: no os.fork on this node')"
srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" -m pytest -q -rs tests/test_benchmarks/test_forkserver.py

echo "Job ${SLURM_JOB_ID}: M0 gate -- step 2/2: validate every RealClassEval task"
srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/validate_realclasseval.py \
    --config "${CONFIG}" \
    --require-python 3.11 \
    --workers "${SLURM_CPUS_PER_TASK:-4}" \
    ${ARGS[@]+"${ARGS[@]}"}
