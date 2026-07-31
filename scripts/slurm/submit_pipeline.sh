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

set -euo pipefail

N_TASKS=163   # 164 tasks: HumanEval indices 0..163

while [[ $# -gt 0 ]]; do
    case $1 in
        --tasks) N_TASKS=$(($2 - 1)); shift 2 ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

ARRAY_RANGE="0-${N_TASKS}"
CPU_SCRIPT="scripts/slurm/submit_cpu.sh"
CPU_SINGLE="scripts/slurm/submit_cpu_single.sh"
LLM_SCRIPT="scripts/slurm/submit_llm.sh"

mkdir -p logs results cache

echo "Submitting Meta-Real-Eval pipeline for task indices 0..${N_TASKS}"
echo "Config: config/default.yaml"
echo ""

S0=$(sbatch --parsable --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" stage0)
echo "Stage 0:          job ${S0}  (array ${ARRAY_RANGE})"

RQ1G=$(sbatch --parsable --dependency=afterok:"${S0}" "${LLM_SCRIPT}" rq1 generate)
echo "RQ1 generate:     job ${RQ1G}  (single, LLM-bound)"

RQ1E=$(sbatch --parsable --dependency=afterok:"${RQ1G}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq1 evaluate)
echo "RQ1 evaluate:     job ${RQ1E}  (array ${ARRAY_RANGE})"

RQ2G=$(sbatch --parsable --dependency=afterok:"${RQ1E}" "${LLM_SCRIPT}" rq2 generate)
echo "RQ2 generate:     job ${RQ2G}  (single, LLM-bound) *** main bottleneck ***"

RQ2E=$(sbatch --parsable --dependency=afterok:"${RQ2G}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq2 evaluate)
echo "RQ2 evaluate:     job ${RQ2E}  (array ${ARRAY_RANGE})"

RQ3X=$(sbatch --parsable --dependency=afterok:"${RQ2E}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq3 execute)
echo "RQ3 execute:      job ${RQ3X}  (array ${ARRAY_RANGE})"

RQ3S=$(sbatch --parsable --dependency=afterok:"${RQ3X}" "${LLM_SCRIPT}" rq3 score)
echo "RQ3 score:        job ${RQ3S}  (single, LLM-bound)"

RQ4D=$(sbatch --parsable --dependency=afterok:"${RQ3S}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq4 degrade)
echo "RQ4 degrade:      job ${RQ4D}  (array ${ARRAY_RANGE})"

RQ4A=$(sbatch --parsable --dependency=afterok:"${RQ4D}" --array="${ARRAY_RANGE}" "${CPU_SCRIPT}" rq4 augment)
echo "RQ4 augment:      job ${RQ4A}  (array ${ARRAY_RANGE})"

RQ4Z=$(sbatch --parsable --dependency=afterok:"${RQ4A}" "${CPU_SINGLE}" rq4 analyze)
echo "RQ4 analyze:      job ${RQ4Z}  (single, CPU-bound)"

echo ""
echo "Pipeline submitted. Final job ID: ${RQ4Z}"
echo "Monitor:  squeue -u \$USER"
echo "Progress: python scripts/progress.py --config config/default.yaml"
