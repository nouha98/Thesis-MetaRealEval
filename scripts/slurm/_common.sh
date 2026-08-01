# Shared setup for all SLURM submission scripts.
#
# Sourced (not executed) from submit_*.sh after the #SBATCH header block.
# Responsibilities:
#   * move to the submit directory
#   * make $HOME-dependent tooling work on nodes where /home is not mounted
#   * locate the venv interpreter
#   * run a preflight check so failures show up as a readable message in the
#     .err file instead of a bare "ExitCode 1"
#
# Everything below writes only inside the project directory on /shared.

# --- 1. Working directory -------------------------------------------------
REPO_DIR="${SLURM_SUBMIT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
cd "${REPO_DIR}"

mkdir -p logs results cache

echo "=== preflight ==========================================="
echo "host:        $(hostname)"
echo "job:         ${SLURM_JOB_ID:-<none>} array-task ${SLURM_ARRAY_TASK_ID:-<none>}"
echo "repo:        ${REPO_DIR}"

# --- 2. HOME / cache redirection -----------------------------------------
# /home is not mounted on the compute nodes of this cluster, so anything that
# writes under $HOME (pip, matplotlib, huggingface, XDG dirs) fails. Point all
# of it at the project directory on /shared.
if [[ -z "${HOME:-}" || ! -d "${HOME}" || ! -w "${HOME}" ]]; then
    export HOME="${REPO_DIR}/.slurm_home"
    mkdir -p "${HOME}"
    echo "HOME:        ${HOME} (redirected — original HOME not usable here)"
else
    echo "HOME:        ${HOME}"
fi

export HF_HOME="${REPO_DIR}/.cache/huggingface"
export XDG_CACHE_HOME="${REPO_DIR}/.cache/xdg"
export MPLCONFIGDIR="${REPO_DIR}/.cache/matplotlib"
mkdir -p "${HF_HOME}" "${XDG_CACHE_HOME}" "${MPLCONFIGDIR}"

# The HumanEval corpus is pre-staged by scripts/fetch_data.py, so no Hub access
# is needed. Force offline mode so a missing route to huggingface.co fails fast
# and loud rather than hanging until the walltime limit.
export HF_HUB_OFFLINE="${HF_HUB_OFFLINE:-1}"
export HF_DATASETS_OFFLINE="${HF_DATASETS_OFFLINE:-1}"

# --- 3. Interpreter -------------------------------------------------------
PY="${REPO_DIR}/.venv/bin/python"
if [[ ! -x "${PY}" ]]; then
    echo "ERROR: no interpreter at ${PY}" >&2
    echo "       Create the environment on the login node with:" >&2
    echo "         python3 -m venv .venv && .venv/bin/pip install -e ." >&2
    exit 1
fi
echo "python:      ${PY} ($("${PY}" --version 2>&1))"

# --- 4. Import + dataset preflight ---------------------------------------
# Both of these are the failure modes that previously produced a silent
# ExitCode 1 within a second of the job starting.
if ! "${PY}" - <<'PYCHECK'
import importlib
import os
import sys

hint = "       Reinstall on the login node with: .venv/bin/pip install -e ."

try:
    import meta_real_eval  # noqa: F401
except Exception as e:
    sys.exit(f"ERROR: cannot import meta_real_eval ({type(e).__name__}: {e}).\n{hint}")

# Importing the runner pulls in every third-party dependency the job needs
# (pydantic, yaml, dotenv, openai, ...). A missing one shows up here with a
# name instead of as a bare ExitCode 1 seconds into the job.
module = os.environ.get("MRE_RUNNER_MODULE")
if module:
    try:
        importlib.import_module(module)
    except Exception as e:
        sys.exit(f"ERROR: cannot import {module} ({type(e).__name__}: {e}).\n{hint}")
    print(f"runner:      {module} imports cleanly")

try:
    from meta_real_eval.core.data_loader import load_humaneval
    tasks = load_humaneval()
except Exception as e:
    sys.exit(f"ERROR: {e}" if type(e).__name__ == "CorpusNotFound"
             else f"ERROR: cannot load HumanEval ({type(e).__name__}: {e})")

print(f"dataset:     {len(tasks)} HumanEval tasks available offline")
PYCHECK
then
    echo "ERROR: preflight failed — aborting before submitting work." >&2
    exit 1
fi
echo "========================================================="

# --- 5. srun flags --------------------------------------------------------
# Slurm >= 22.05 no longer propagates --cpus-per-task from sbatch to srun.
SRUN_ARGS=()
if [[ -n "${SLURM_CPUS_PER_TASK:-}" ]]; then
    SRUN_ARGS+=("--cpus-per-task=${SLURM_CPUS_PER_TASK}")
fi
