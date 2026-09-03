#!/bin/bash
# LLM-bound single job: regenerate only the persona family of the RQ2 paraphrase
# corpus (scripts/regenerate_persona_family.py). Not part of the
# <stage>.runner --phase pipeline, so this forwards its own flags directly,
# same as submit_paraphrase_corpus.sh.
#
# Usage:
#   sbatch scripts/slurm/submit_regenerate_persona.sh              # apply
#   sbatch scripts/slurm/submit_regenerate_persona.sh --dry-run    # report only, no LLM calls
#
# When it finishes, logs/slurm_<jobid>.out ends with the same summary
# generate_paraphrases.py prints: variants filled/expected, per-family
# coverage, and the (new) sha256 to paste into rq2.corpus_sha256 -- this WILL
# differ from whatever value is there now.
#
#SBATCH --job-name=regenerate_persona
#SBATCH --cpus-per-task=2
#SBATCH --time=12:00:00
#SBATCH --output=logs/slurm_%j.out
#SBATCH --error=logs/slurm_%j.err

set -euo pipefail

export MRE_RUNNER_MODULE="meta_real_eval.rq2.corpus"
source "${SLURM_SUBMIT_DIR:-$(dirname "$0")/../..}/scripts/slurm/_common.sh"

echo "Job ${SLURM_JOB_ID}: regenerate RQ2 persona family"

srun ${SRUN_ARGS[@]+"${SRUN_ARGS[@]}"} "${PY}" scripts/regenerate_persona_family.py \
    --config config/default.yaml \
    "$@"
