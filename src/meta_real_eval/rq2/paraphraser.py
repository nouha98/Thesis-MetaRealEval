"""Deterministic metamorphic prompt transforms.

Five relations are applied to each HumanEval task prompt to produce
semantically equivalent prompt variants.  All transforms are template-based
and require no LLM calls, making them free and fully reproducible.

Relations
---------
original   MR-Original  — prompt returned unchanged (baseline)
persona    MR-Persona   — expert framing prepended
formal     MR-Formal    — passive / structured reformulation of docstring
reorder    MR-Reorder   — examples moved before description
terse      MR-Terse     — removal of filler phrases
"""

from __future__ import annotations

import re


_PERSONA_PREFIX = (
    "As a senior Python engineer with expertise in algorithms and data structures, "
    "complete the following function according to its specification:\n\n"
)

_FILLER_PATTERNS = [
    r"\bPlease\b",
    r"\bNote that\b",
    r"\bNote:\b",
    r"\bRemember\b",
    r"\bMake sure\b",
    r"\bYou should\b",
    r"\bDon't forget\b",
    r"\bKeep in mind\b",
    r"(?i)\bfor example\b,?\s*",
]


def _split_docstring(prompt: str) -> tuple[str, str, str]:
    """Return (signature, description, examples).

    Handles docstrings where text follows the opening triple-quote on the same
    line (e.g. a docstring that opens and immediately starts with description
    text).  In that case the inline text is treated as the start of the
    description, not part of the signature.
    """
    lines = prompt.splitlines(keepends=True)
    try:
        open_idx = next(i for i, l in enumerate(lines) if '"""' in l or "'''" in l)
    except StopIteration:
        return prompt, "", ""

    open_line = lines[open_idx]
    quote_char = '"""' if '"""' in open_line else "'''"
    quote_pos = open_line.index(quote_char)
    after_quote = open_line[quote_pos + 3:].strip()

    if after_quote and after_quote != quote_char:
        # Description starts on the same line as the opening triple-quote.
        # Keep only up to (and including) the quotes in the signature.
        signature = "".join(lines[:open_idx]) + open_line[:quote_pos + 3] + "\n"
        rest_content = after_quote + "\n" + "".join(lines[open_idx + 1:])
    else:
        signature = "".join(lines[:open_idx + 1])
        rest_content = "".join(lines[open_idx + 1:])

    rest_lines = rest_content.splitlines(keepends=True)
    example_start = None
    for i, line in enumerate(rest_lines):
        if line.strip().startswith(">>>"):
            example_start = i
            break

    if example_start is None:
        return signature, rest_content, ""

    description = "".join(rest_lines[:example_start])
    examples = "".join(rest_lines[example_start:])
    return signature, description, examples


def apply_relation(prompt: str, relation: str) -> str:
    """Return the transformed prompt for the given relation name."""
    if relation == "original":
        return prompt

    if relation == "persona":
        return _PERSONA_PREFIX + prompt

    if relation == "formal":
        # Passive-voice framing: add a formal preamble after the signature line
        sig, desc, examples = _split_docstring(prompt)
        formal_preamble = (
            "    [Specification]\n"
            "    The function must satisfy the following requirements:\n\n"
        )
        return sig + formal_preamble + desc + examples

    if relation == "reorder":
        # Move examples before description (shuffle context order)
        sig, desc, examples = _split_docstring(prompt)
        if examples:
            return sig + examples + desc
        return prompt  # nothing to reorder

    if relation == "terse":
        cleaned = prompt
        for pattern in _FILLER_PATTERNS:
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
        # Collapse multiple blank lines to one
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned

    raise ValueError(f"Unknown relation: {relation!r}")


def apply_all_relations(prompt: str, relations: list[str]) -> dict[str, str]:
    """Return {relation_name: transformed_prompt} for every relation."""
    return {rel: apply_relation(prompt, rel) for rel in relations}
