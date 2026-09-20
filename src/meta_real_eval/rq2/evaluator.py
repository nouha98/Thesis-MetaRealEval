"""RQ2 evaluate phase: execute completions against the test suite and compute Pass@k.

Pass@k uses the unbiased estimator from Chen et al. 2021 (HumanEval paper):

    pass@k = 1 - C(n-c, k) / C(n, k)

where n = total samples, c = correct samples.
"""

from __future__ import annotations

import ast
import logging
import math
import re
import textwrap
from concurrent.futures import ProcessPoolExecutor
from typing import Callable

from ..core.checkpoint import clear_done, is_done, mark_done, task_dir, write_json, read_json
from ..core.config import Config
from ..core.data_loader import HumanEvalTask, task_label
from ..core.sandbox import execute

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pass@k estimator
# ---------------------------------------------------------------------------

def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator.  Returns 1.0 if n - c < k."""
    if n == 0:
        return 0.0
    if n - c < k:
        return 1.0
    return 1.0 - math.prod((n - c - i) / (n - i) for i in range(k))


# ---------------------------------------------------------------------------
# Code extraction
# ---------------------------------------------------------------------------
#
# Whether a completion is a *body* (to be appended to the task prompt) or a
# *complete module* (to be run on its own) decides what source gets executed, so
# getting it wrong silently scores a correct solution as wrong.  The decision is
# made by parsing, never by pattern-matching the first characters:
#
#   re.match(r"\s*def\s+", body)
#
# accepted a leading indent, so a body-only completion opening with a nested
# helper ("    def f(x): ...") was read as a complete module, run without the
# prompt, and died with IndentationError.  That was 924 of 24 600 completions in
# the pilot corpus - and unevenly distributed across models, which is exactly the
# kind of bias RQ2's ranking analysis cannot absorb.

_FENCE_RE = re.compile(r"```[A-Za-z0-9_+-]*\s*(.*?)```", re.DOTALL)
_OPEN_FENCE_RE = re.compile(r"```[A-Za-z0-9_+-]*[ \t]*\r?\n")


def _strip_markdown(raw: str) -> str:
    """Return the code inside a markdown fence, if the completion used one."""
    fenced = _FENCE_RE.search(raw)
    if fenced:
        return fenced.group(1)
    # Truncated generation: an opening fence with no closing one.  Everything
    # after it is still code, and the ``` line itself is not.
    open_fence = _OPEN_FENCE_RE.search(raw)
    if open_fence:
        return raw[open_fence.end():]
    return raw


def _defines_entry_point(code: str, entry_point: str) -> bool:
    """True if `code` parses and defines `entry_point` at module level.

    Module level matters: a nested helper of the same name would not be callable
    by the test driver, and indented source does not parse at all.
    """
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == entry_point
        for node in tree.body
    )


def _assembles_cleanly(code: str, entry_point: str) -> bool:
    """True if `code` parses AND nothing leaked out past the entry-point def.

    Stricter than :func:`_defines_entry_point`, and only meaningful on the
    body-only path, where the body is appended *inside* the prompt's function.
    Parsing alone is too weak an acceptance test there: a flat body appended to
    the prompt can parse perfectly well with its statements sitting at module
    level next to the function rather than inside it, and then die at run time
    with NameError -- which scores as a wrong answer rather than a crash, so it
    would hide from exactly the failure-mode audit that is supposed to catch it.

    Requiring the entry-point definition to be the LAST top-level statement is
    what rules that out: if any of the body escaped, it shows up as a sibling
    statement after the def. Not valid on the module path, where a completion
    may legitimately define a helper below the entry point.
    """
    try:
        module = ast.parse(code)
    except (SyntaxError, ValueError):
        return False
    indices = [
        i for i, node in enumerate(module.body)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == entry_point
    ]
    return bool(indices) and indices[-1] == len(module.body) - 1


# Candidate repairs for a body-only completion, in priority order.
#
# Models do not reliably emit the 4-space indent that makes a body a body, and
# they get it wrong in two incompatible ways, so no single repair works.
# Measured over the gemma corpus (1,637 body-only completions):
#
#   shape                  n    as-is   first+4   uniform+4
#   already-indented     623     100%        0%          0%
#   first line at 0,     389       2%       93%         10%
#     rest >= 4
#   fully flat           296       0%        0%        100%
#   single line at 0     261       0%      100%        100%
#   single line at 4      68     100%        0%          0%
#
# "first+4" restores an indent dropped from the first line only, leaving the
# already-correct continuation lines where they are. "uniform+4" shifts the
# whole block, for a body that was dedented as a unit. Each is wrong for the
# other's shape, so the two are tried in turn and the first candidate that
# assembles cleanly wins. Trying as-is FIRST guarantees no regression: a
# well-formed body is never touched.
#
# Verified over the same corpus: this repairs 945 of the 946 broken bodies, and
# NO completion is accepted by two rungs that produce different ASTs -- so the
# ladder is deterministic and never has to guess between rival repairs.
_REPAIR_LADDER: tuple[tuple[str, Callable[[str], str]], ...] = (
    ("as-is",     lambda body: body),
    ("first+4",   lambda body: "    " + body),
    ("uniform+4", lambda body: textwrap.indent(body, "    ")),
)


def assemble_body(body: str, task_prompt: str, entry_point: str) -> tuple[str, str]:
    """Append a body-only completion to its prompt, repairing indentation.

    Returns ``(assembled_source, rung)`` where ``rung`` names the repair that
    was accepted, or ``"unrepaired"`` when none assembled cleanly. Callers that
    do not care about the rung use :func:`build_solution_code`; the rung is
    exposed so a verification pass can report how often each repair fires, and
    flag any completion that two rungs disagree over.
    """
    for rung, repair in _REPAIR_LADDER:
        candidate = task_prompt + repair(body)
        if _assembles_cleanly(candidate, entry_point):
            return candidate, rung
    # Nothing worked. Hand back the plain concatenation -- the pre-repair
    # behaviour -- so the completion fails the same way it always did rather
    # than failing differently because of a speculative fix.
    return task_prompt + body, "unrepaired"


def _prompt_helpers(task_prompt: str, code: str, entry_point: str) -> list[str]:
    """Helper functions the prompt defines that a module completion left out.

    HumanEval/10, /32, /38 and /50 define a helper above the entry point
    (``is_palindrome``, ``poly``, ``encode_cyclic``, ``encode_shift``) and the
    task's own tests call through it. A completion that restates the entry point
    as a whole module but not the helper raises NameError -- a harness artifact,
    not a wrong answer. This is the same reasoning as :func:`_prompt_imports`,
    applied to definitions instead of imports.

    The entry point itself is never re-attached: the completion supplies it, and
    the prompt's copy has no body beyond the docstring.
    """
    try:
        prompt_tree = ast.parse(task_prompt)
        code_tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return []
    already_defined = {
        node.name for node in code_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    return [
        ast.unparse(node) for node in prompt_tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name != entry_point
        and node.name not in already_defined
    ]


def _prompt_imports(task_prompt: str) -> list[str]:
    """Top-level import statements the task prompt supplies.

    HumanEval prompts often open with `import math` or `from typing import List`
    above the signature.  A completion that restates the whole function but not
    those imports needs them re-attached or it raises NameError.
    """
    try:
        tree = ast.parse(task_prompt)
    except (SyntaxError, ValueError):
        return [ln for ln in task_prompt.splitlines()
                if ln.startswith(("import ", "from "))]
    return [ast.unparse(node) for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom))]


def _extract_function_body(raw: str, entry_point: str) -> str:
    """Extract the runnable code from a model completion.

    Models may return just the body (indented lines), a complete module, or
    either wrapped in a markdown fence.  A complete module is returned *whole* -
    including any imports and helper definitions above the entry point, which an
    earlier version sliced away at the `def` line.
    """
    src = _strip_markdown(raw)

    lines = src.splitlines()
    def_pattern = re.compile(rf"[ \t]*def\s+{re.escape(entry_point)}\s*\(")
    def_index = next(
        (i for i, line in enumerate(lines) if def_pattern.match(line)), None
    )
    if def_index is None:
        return src                      # body-only completion

    # Keep as much of the prefix as still parses.  Starting at 0 keeps imports
    # and helper functions; later starts drop prose, stray fences, or a
    # truncated leading statement that would make the module unparseable.
    for start in range(def_index + 1):
        candidate = "\n".join(lines[start:])
        if _defines_entry_point(candidate, entry_point):
            return candidate

    # Nothing parses (e.g. the def is indented, so this is really a body).
    # Hand back the original text and let build_solution_code() prepend the
    # prompt, rather than slicing at the def and guaranteeing a syntax error.
    return src


def build_solution_code(completion: str, task_prompt: str, entry_point: str) -> str:
    """Assemble the module source to execute for one completion.

    Single source of truth for the body-vs-module decision, shared by RQ2's
    evaluator and RQ3's divergence/SBC paths so all three score a completion
    the same way.
    """
    code = _extract_function_body(completion, entry_point)

    if not _defines_entry_point(code, entry_point):
        # Body-only: the prompt supplies the signature and the imports, and the
        # body's indentation is repaired if the model dropped it (see
        # _REPAIR_LADDER).
        assembled, _rung = assemble_body(code, task_prompt, entry_point)
        return assembled

    # Complete module: re-attach what the prompt supplied and the completion
    # did not restate -- imports, then any helper defined above the entry point.
    # Repeating an import the model already wrote is harmless, so the imports
    # need no de-duplication; helpers do, or we would shadow the model's own.
    prelude = _prompt_imports(task_prompt) + _prompt_helpers(task_prompt, code, entry_point)
    return ("\n".join(prelude) + "\n" + code) if prelude else code


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def _run_completion(
    completion: str,
    task_prompt: str,
    test_code: str,
    entry_point: str,
    timeout_s: float,
) -> bool:
    """Return True if the completion passes the test."""
    solution_code = build_solution_code(completion, task_prompt, entry_point)

    test = test_code + f"\ncheck({entry_point})\n"
    result = execute(solution_code, test, timeout_s=timeout_s)
    return result.passed


def evaluate_task(task: HumanEvalTask, cfg: Config, force: bool = False) -> None:
    """Evaluate cached completions for one task and write pass rates."""
    label = task_label(task)
    out = task_dir(cfg, "rq2", label, phase="evaluate")

    if force:
        # Also wipes rankings.json (computed downstream from pass_rates.json
        # in this same directory), so the ranking step redoes its work too.
        clear_done(out)

    if is_done(out):
        logger.info("SKIP evaluate %s", label)
        return

    gen_out = task_dir(cfg, "rq2", label, phase="generate")
    try:
        completions_data: dict = read_json(gen_out, "completions.json")
    except FileNotFoundError:
        logger.error("Missing generate output for %s — run rq2 generate first", label)
        return

    pass_rates: dict[str, dict[str, dict]] = {}

    # One pool for the whole task, not one per (relation, model) cell. At ~21
    # relations x 3 models that was 63 pool spin-ups per task and ~10k over the
    # corpus, each paying Windows process-creation cost for 10 subprocess
    # launches of actual work.
    with ProcessPoolExecutor(max_workers=cfg.execution.cpu_workers) as pool:
        futures_by_cell: dict[tuple[str, str], list] = {}
        for relation, model_completions in completions_data.items():
            pass_rates[relation] = {}
            for model_id, completions in model_completions.items():
                futures_by_cell[(relation, model_id)] = [
                    pool.submit(
                        _run_completion,
                        comp,
                        task.prompt,
                        task.test,
                        task.entry_point,
                        cfg.execution.timeout_s,
                    )
                    for comp in completions
                ]

        # Collected in submission order (not as_completed) so per_completion[i]
        # refers to completions[i].  RQ3 scores divergence as a classifier of
        # "this solution passes the benchmark", which needs the individual
        # outcomes — they were previously summed away and thrown out.
        for (relation, model_id), futures in futures_by_cell.items():
            per_completion = []
            for f in futures:
                try:
                    per_completion.append(bool(f.result()))
                except Exception:
                    per_completion.append(False)
            n = len(per_completion)
            correct = sum(per_completion)

            pass_rates[relation][model_id] = {
                "n": n,
                "correct": correct,
                "per_completion": per_completion,
                "pass@1":  pass_at_k(n, correct, 1),
                "pass@5":  pass_at_k(n, correct, 5),
                "pass@10": pass_at_k(n, correct, 10),
            }
            logger.debug("  %s / %s / %s: pass@1=%.3f",
                         label, relation, model_id,
                         pass_rates[relation][model_id]["pass@1"])

    write_json(out, "pass_rates.json", pass_rates)
    mark_done(out)
    logger.info("Evaluated %s", label)
