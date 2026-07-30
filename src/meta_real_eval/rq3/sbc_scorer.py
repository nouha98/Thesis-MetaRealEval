"""RQ3 score phase: SBC (Semantic-BLEU-Completeness) scoring via reverse generation.

We ask the LLM to infer the requirements from each generated solution
(reverse generation), then compare the inferred spec against the original
task description on three dimensions:

- Semantic similarity (embedding cosine or LLM-judged)
- BLEU score between inferred and original spec
- Completeness score (fraction of key concepts covered)

This provides a false-positive detection signal independent of fixed oracles.
"""

from __future__ import annotations

import logging
import re

import numpy as np

from ..core.data_loader import HumanEvalTask
from ..core.llm_client import InnkubeClient

logger = logging.getLogger(__name__)

_REVERSE_GEN_SYSTEM = (
    "You are a software specification analyst. "
    "Given a Python function implementation, infer and describe its intended specification "
    "in 2-4 clear sentences. Describe what the function is supposed to do, "
    "including edge cases it handles. Do not reference implementation details."
)


def _bleu_1gram(reference: str, hypothesis: str) -> float:
    """Unigram BLEU approximation (no NLTK dependency)."""
    ref_tokens = set(reference.lower().split())
    hyp_tokens = hypothesis.lower().split()
    if not hyp_tokens:
        return 0.0
    matches = sum(1 for t in hyp_tokens if t in ref_tokens)
    return matches / len(hyp_tokens)


def _completeness_score(original_docstring: str, inferred_spec: str) -> float:
    """Fraction of non-trivial words from docstring present in inferred spec."""
    stopwords = {"the", "a", "an", "is", "it", "of", "to", "and", "or", "in",
                 "that", "this", "with", "for", "are", "be", "as", "from"}
    ref_words = {
        w.lower().strip(".,;:()[]")
        for w in original_docstring.split()
        if len(w) > 3 and w.lower() not in stopwords
    }
    if not ref_words:
        return 1.0
    inferred_lower = inferred_spec.lower()
    covered = sum(1 for w in ref_words if w in inferred_lower)
    return covered / len(ref_words)


async def compute_sbc_score(
    task: HumanEvalTask,
    solution_code: str,
    model_id: str,
    client: InnkubeClient,
) -> dict:
    """Return SBC scores for one solution."""
    messages = [
        {"role": "system", "content": _REVERSE_GEN_SYSTEM},
        {"role": "user", "content": f"Function implementation:\n\n{solution_code}"},
    ]

    try:
        responses = await client.complete(
            model=model_id,
            messages=messages,
            temperature=0.3,
            max_tokens=256,
            n=1,
        )
        inferred_spec = responses[0] if responses else ""
    except Exception as exc:
        logger.warning("SBC reverse generation failed: %s", exc)
        inferred_spec = ""

    # Extract original docstring as reference
    docstring_match = re.search(r'"""(.*?)"""', task.prompt, re.DOTALL)
    original_spec = docstring_match.group(1).strip() if docstring_match else task.prompt

    bleu = _bleu_1gram(original_spec, inferred_spec)
    completeness = _completeness_score(original_spec, inferred_spec)
    # Semantic score: proxy via BLEU on bigrams (simple, no embedding needed)
    ref_bigrams = set(zip(original_spec.lower().split(), original_spec.lower().split()[1:]))
    hyp_bigrams = list(zip(inferred_spec.lower().split(), inferred_spec.lower().split()[1:]))
    semantic = (
        sum(1 for b in hyp_bigrams if b in ref_bigrams) / len(hyp_bigrams)
        if hyp_bigrams else 0.0
    )
    sbc = (semantic + bleu + completeness) / 3.0

    return {
        "inferred_spec": inferred_spec,
        "semantic_score": round(semantic, 4),
        "bleu_score": round(bleu, 4),
        "completeness_score": round(completeness, 4),
        "sbc_score": round(sbc, 4),
    }
