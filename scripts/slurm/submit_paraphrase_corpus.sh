#!/bin/bash
# LLM-bound single job: build the RQ2 paraphrase corpus (scripts/generate_paraphrases.py).
# Not part of the <stage>.runner --phase pipeline, so this forwards its own flags
# directly instead of taking <stage> <phase> like submit_llm.sh.
#
# Usage:
#   sbatch scripts/slurm/submit_paraphrase_corpus.sh                    # all 164 tasks
#   sbatch scripts/slurm/submit_paraphrase_corpus.sh --task-range 0-19  # pilot subset
#
# When it finishes, logs/slurm_<jobid>.out ends with the same summary
# generate_paraphrases.py always prints: tasks, variants filled/expected,
# per-family coverage, and the sha256 to paste into rq2.corpus_sha256.
#
#SBATCH --job-name=submit_paraphrase_corpus
#SBATCH --cpus-per-task=2
#SBATCH --time=24:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

# Not a <stage>.runner module, but generate_paraphrases.py imports rq2.corpus directly,
# so checking that import still gets the same "fail fast with a readable message"
# preflight the other scripts get, rather than a bare ExitCode 1 an hour in.
export MRE_RUNNER_MODULE="meta_real_eval.rq2.corpus"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

echo "Job ${SLURM_JOB_ID}: build RQ2 paraphrase corpus"

srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/generate_paraphrases.py \
    --config config/default.yaml \
    "$@"