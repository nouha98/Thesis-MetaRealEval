"""Generate LLM-specific (semantic) mutants via Innkube.

LLMorpheus-style approach: ask the model to introduce a subtle, realistic
fault that a competent programmer might write — wrong logic, hallucinated
API calls, off-by-one edge cases — while keeping the code syntactically valid.
"""

from __future__ import annotations

import asyncio
import logging
import re

from ..core.data_loader import HumanEvalTask
from ..core.llm_client import InnkubeClient
from ..stage0.corpus_builder import Mutant

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a Python mutation testing expert. "
    "Given a correct Python function, introduce exactly ONE subtle semantic fault. "
    "The fault must be realistic (a mistake a developer might make), keep the code "
    "syntactically valid, and NOT be a trivial operator swap. "
    "Return only the complete modified function — no explanation, no markdown fences."
)


def _build_user_message(task: HumanEvalTask) -> str:
    return (
        f"Introduce one subtle semantic fault into this function:\n\n"
        f"{task.prompt}{task.canonical_solution}"
    )


def _extract_code(raw: str, prompt: str) -> str | None:
    """Strip markdown fences if present and validate that code parses."""
    import ast

    code = raw.strip()
    # Remove ```python ... ``` fences
    fenced = re.match(r"```(?:python)?\s*(.*?)```", code, re.DOTALL)
    if fenced:
        code = fenced.group(1).strip()

    try:
        ast.parse(code)
        return code
    except SyntaxError:
        return None


async def generate_llm_mutants(
    task: HumanEvalTask,
    model_id: str,
    client: InnkubeClient,
    n_mutants: int = 3,
) -> list[Mutant]:
    """Ask the LLM to generate n_mutants semantic mutants for one task."""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_user_message(task)},
    ]

    # Request more than needed to account for parse failures
    try:
        raw_completions = await client.complete(
            model=model_id,
            messages=messages,
            temperature=0.9,
            max_tokens=1024,
            n=n_mutants + 2,
        )
    except Exception as exc:
        logger.warning("LLM mutant generation failed for %s: %s", task.task_id, exc)
        return []

    mutants: list[Mutant] = []
    for idx, raw in enumerate(raw_completions):
        code = _extract_code(raw, task.prompt)
        if code is None:
            logger.debug("Skipping unparseable LLM mutant %d for %s", idx, task.task_id)
            continue
        # Skip if identical to canonical
        if code.strip() == (task.prompt + task.canonical_solution).strip():
            continue
        mutants.append(Mutant(
            mutant_id=f"LLM_{idx}",
            operator="LLM",
            description=f"LLM-generated semantic mutant (model={model_id})",
            code=code,
        ))
        if len(mutants) >= n_mutants:
            break

    logger.info("Generated %d LLM mutants for %s", len(mutants), task.task_id)
    return mutants
