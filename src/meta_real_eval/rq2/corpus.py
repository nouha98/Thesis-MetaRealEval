"""RQ2 paraphrase corpus: LLM-rewritten prompt variants, generated once and reused.

Why this module exists
----------------------
The template relations in :mod:`.paraphraser` do not reword the specification at
all: ``persona`` and ``formal`` only prepend a preamble, ``reorder`` moves ``>>>``
blocks, and ``terse`` strips filler phrases that HumanEval docstrings mostly do
not contain.  Measured over all 164 prompts, ``reorder`` is a no-op on 88 of them
and ``terse`` on 103.  When a relation is a no-op the generator builds a
byte-identical ``messages`` list, :meth:`ResponseCache.key` hashes to the same
value, and the cell comes back with *the same completions as* ``original`` — so
its Kendall tau_b is 1.0 by construction.  191 of 656 (task, relation) cells in
the 164-task run measured nothing at all.

This module generates real rewrites with an LLM instead, once, into a committed
data artifact (``data/paraphrases/humaneval_v1.json``) that every model under
test then reads.  Reproducibility is claimed for *the corpus as a versioned
artifact*, verified by SHA-256 — not for the generation procedure, which is a
sampled LLM call and is not reproducible by a seed (``InnkubeClient`` never sends
one, and on an OpenAI-compatible vLLM gateway it would be best-effort anyway).

Splice, don't ask
-----------------
The generator is never asked to *reproduce* the imports, any helper function, the
entry point's own ``def`` line, or the docstring's opening/closing quotes.
:func:`split_spec` cuts those out of the prompt deterministically and
:func:`assemble` splices them back in verbatim after the model rewrites only the
docstring's prose and examples (:data:`PROMPT_TEMPLATE_VERSION` 2 and later).  The
model cannot corrupt what it never sees.

This was not the original design (v1 asked for a byte-for-byte reproduction of
everything around the docstring).  A 2-task pilot on the 4 HumanEval tasks that
define a helper function ahead of the entry point (``10, 32, 38, 50``) put 175
candidates through Gate A: 104 (59%) failed `signature_not_verbatim` and 12 (7%)
failed `text_before_signature` — one model asked to retype several hundred bytes
of code character-for-character while also rewriting prose around it, failing at
the retyping. Only 15 (9%) — `duplicate_of_sibling` — actually measured output
diversity. Splicing targets the 66%, not the 9%.

Validation
----------
Gate A (:func:`structural_gate`) — mechanical, free, runs first.  Rejects a
candidate that moved the signature, dropped an example, invented a number, does
not parse, duplicates a sibling, or is byte-identical to the original.  That last
one is the defect above, asserted rather than assumed.  Under the splice design,
`signature_not_verbatim`, `text_before_signature`, `extra_def_introduced` and
`function_body_written` should be unreachable by construction — `assemble()`
guarantees the spliced parts are byte-identical to the original and that no
family but `persona` can introduce a preamble.  A non-zero count for any of them
now indicates a bug in `split_spec`/`assemble`, not a model failure; they stay in
Gate A as a defensive backstop (persona's framing text, or a model that sneaks a
`def` into its rewritten prose despite being told not to, are both still real
possibilities), and the manifest's coverage block is where a regression there
would first show up as a drop in filled families.

Gate B (:func:`judge_candidate`) — a **held-out** model, one that is not in
``cfg.llm.models``, rules the rewrite EQUIVALENT / NOT_EQUIVALENT / UNSURE.
Judging with the models being ranked would filter on the dependent variable and
drive RQ2 toward a null by construction, so the judge must sit outside the
comparison.

Gate C is manual: ``scripts/paraphrase_report.py`` emits a stratified sample for
human review.  It is a validity statistic for the write-up, not a code gate.

A family that cannot be filled after :data:`MAX_REGEN` attempts leaves its slots
**absent** — the same missing-not-imputed discipline as the rest of the pipeline.
It is never padded with a template, which would silently reintroduce the very
cells this module exists to remove.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Optional

from ..core.data_loader import HumanEvalTask
from ..core.llm_client import InnkubeClient

logger = logging.getLogger(__name__)

CORPUS_VERSION = "v1"
# 1 = ask for byte-for-byte reproduction; 2 = splice; 3 = splice, and the
# `formal` instruction forbids inventing numeric bounds.  Version 3 exists
# because `formal` was by far the worst-filled family in the 8-task pilot
# (12/24 slots, and the only family that left a task with zero variants at all),
# and both of its dominant failure modes were the same behaviour: 33
# `new_numeric_literal` rejections, almost all introducing 0 / 0.0 / 1.0, and
# judge verdicts reading "adds the requirement that the threshold must be
# positive".  The formal register was strengthening the contract, not just the
# prose.  Gate A and the judge were both right to reject those; the fix belongs
# in the instruction, so the family fills instead of silently thinning the
# corpus on exactly the tasks that carry numeric arguments.
PROMPT_TEMPLATE_VERSION = 3

FAMILIES = ["lexical", "reorder", "formal", "persona", "terse"]
N_PER_FAMILY = 3

# A task enters the primary RQ2 analysis only once at least this many of the 5
# families have >=1 accepted variant.  Below this, a task's LLM-arm mean would be
# computed over so few families that one easy/hard family could dominate it, and
# comparing such a task's LLM arm against its (always-complete) template arm would
# not be a fair comparison.  See scripts/analyze_results.py's coverage filter and
# the paired understatement statistic.
#
# Counted on families that were GENERATED, never on families that went on to
# produce a defined Kendall tau_b.  A fully generated family yields no tau_b
# exactly when every model ties under it — i.e. on the tasks whose ranking was
# most stable — so gating on the tau count would select against stable tasks and
# bias the surviving mean tau_b downward, which is filtering on the dependent
# variable.  rq2/ranking.py writes the two counts under separate keys
# (`n_families_generated` vs `n_families_with_defined_tau`) so they cannot be
# confused again; analyze_results.py gates on the first and reports the second.
#
# The threshold shrinks the analysed sample, so it is never reported alone:
# analyze_results.py emits `coverage_sensitivity`, the same headline recomputed
# ungated (>=1 family), at this threshold, and complete-case (5/5).  Agreement
# across the three is the evidence that the conclusion is not an artefact of the
# subset that survives the gate.
MIN_FAMILIES_COVERED = 4

# Mirrors the RQ1 mutant-generation retry budget.  Each attempt re-requests the
# whole family; without a cache_salt the second attempt would replay the first
# attempt's cached completions verbatim and the budget would buy nothing.
MAX_REGEN = 4

JUDGE_VERDICTS = ("EQUIVALENT", "NOT_EQUIVALENT", "UNSURE")

# Generous on purpose: the held-out models available on this Innkube endpoint
# reason before answering (either in a separate reasoning_content field or
# inline, closed by </think> -- see InnkubeClient._strip_reasoning), and a real
# HumanEval-length rewrite needs room for that on top of the rewrite itself. A
# low budget silently returns empty content (finish_reason="length", 0 tokens
# left for the answer), which reads to Gate A as every candidate being "empty"
# rather than as a truncated response. Verified empirically before these were
# picked (soofi-s-isar-preview needs up to ~8000 tokens on harder tasks).
# Named constants, not inline literals, so scripts/generate_paraphrases.py can
# record the values actually used in the corpus manifest instead of a value
# that silently drifts from what generate_family really sends.
GENERATION_TEMPERATURE = 0.7
GENERATION_MAX_TOKENS = 8192
JUDGE_MAX_TOKENS = 4096


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

# Not shown to the model as a literal keyword instruction in the prose sense --
# it is a wire-format marker in the persona system prompt, parsed back out by
# _parse_persona_response. Chosen to be something a rewrite would never
# naturally contain.
_PERSONA_SENTINEL = "---BODY---"

_SYSTEM_PROMPT = (
    "You rewrite the prose and examples inside a Python function's docstring -- "
    "nothing else. You are given CONTEXT (the function's signature, and any helper "
    "function it relies on) purely so you understand what the function does and can "
    "write a coherent, accurate rewrite. You do NOT reproduce any part of CONTEXT.\n\n"
    "Your entire response is the rewritten docstring content, and nothing but that: "
    "no imports, no def line, no opening or closing triple-quote, no markdown fences, "
    "no preamble such as 'Here is the rewritten text:', no narration of what you are "
    "about to do or did do, no restating these instructions. If you need to reason "
    "about the rewrite, do that reasoning silently.\n\n"
    "Hard invariants - breaking any one makes your output unusable:\n"
    "- Reproduce every >>> line and every expected-output line EXACTLY, character for "
    "character. Do not add examples and do not drop any.\n"
    "- Do not add, remove, weaken, or strengthen a single requirement. The set of "
    "inputs accepted and the outputs produced must be identical to CONTEXT's function.\n"
    "- Do not introduce any number that is not already present in CONTEXT or the text "
    "you were given to rewrite.\n"
    "- Do not write a function body, and do not repeat the signature or any other part "
    "of CONTEXT verbatim as if it were part of your answer."
)

_PERSONA_SYSTEM_PROMPT = (
    "You do two things with a Python function's docstring. You are given CONTEXT "
    "(the function's signature, and any helper function it relies on) purely so you "
    "understand what the function does; you do NOT reproduce any part of CONTEXT.\n\n"
    "1. Write a short framing paragraph addressed to the implementer -- casting them "
    "in a role, or setting a scenario in which this function is needed.\n"
    "2. Rewrite the docstring's prose and examples in a voice that matches that "
    "framing.\n\n"
    f"Respond with the framing paragraph, then a line containing exactly "
    f"'{_PERSONA_SENTINEL}' and nothing else, then the rewritten docstring content. "
    "Nothing else in your response: no imports, no def line, no triple-quotes, no "
    "markdown fences, no preamble, no narration, no restating these instructions.\n\n"
    "Hard invariants for part 2, the rewritten docstring content - breaking any one "
    "makes your output unusable:\n"
    "- Reproduce every >>> line and every expected-output line EXACTLY, character for "
    "character. Do not add examples and do not drop any.\n"
    "- Do not add, remove, weaken, or strengthen a single requirement.\n"
    "- Do not introduce any number that is not already present in CONTEXT or the text "
    "you were given to rewrite.\n"
    "- Do not write a function body, and do not repeat the signature or any other part "
    "of CONTEXT verbatim as if it were part of your answer."
)

_FAMILY_INSTRUCTIONS = {
    "lexical": (
        "Rewrite the prose using different vocabulary and different sentence "
        "structure while preserving the exact programming requirements. Substitute "
        "synonyms and recast phrasings; do not merely reorder the existing words."
    ),
    "reorder": (
        "Rewrite so the information arrives in a different order: put the examples "
        "before the prose description, and where the description has several "
        "clauses or constraints, present them in a different sequence. The wording "
        "of each individual requirement may stay close to the original; what must "
        "change is the order in which the reader meets them."
    ),
    "formal": (
        "Rewrite in a formal specification register: passive or impersonal voice, "
        "precise technical terms, requirements stated as explicit conditions on "
        "inputs and outputs. It should read like a written standard rather than an "
        "informal note to a colleague. State only the conditions the original "
        "already states: do NOT add ranges, bounds, sign restrictions, cardinalities "
        "or index limits (no 'greater than 0', no 'in the interval [0.0, 1.0]', no "
        "'must be positive', no 'of length at least 1') unless that exact "
        "restriction is written in the text you were given. Formalising the register "
        "must not formalise the contract."
    ),
    "persona": (
        "Cast the implementer in a role, or set a scenario in which this function "
        "is needed, then give the docstring's prose and examples in a voice that "
        "matches that framing."
    ),
    "terse": (
        "Rewrite as tersely as possible: strip every word that does not carry a "
        "requirement, prefer clipped noun phrases over full sentences, and drop "
        "hedging and pleasantries. Every constraint present in the original must "
        "survive the compression - terse, not incomplete. Every >>> example line is "
        "still reproduced exactly regardless of how terse the prose becomes."
    ),
}

_JUDGE_SYSTEM_PROMPT = (
    "You check whether two versions of a programming task specification demand exactly "
    "the same function.\n\n"
    "Answer on the first line with exactly one of:\n"
    "EQUIVALENT\nNOT_EQUIVALENT\nUNSURE\n\n"
    "On the second line give a one-sentence reason.\n\n"
    "Answer NOT_EQUIVALENT if the rewrite adds, drops, weakens, or strengthens any "
    "requirement; changes the type or meaning of an argument or of the return value; "
    "changes any example; or changes the behaviour required on any input. Wording, tone, "
    "register, and the order in which requirements are presented are NOT differences in "
    "meaning. Answer UNSURE only if the rewrite is genuinely ambiguous about a requirement "
    "that the original settles."
)


def _build_generation_messages(prefix: str, body: str, family: str) -> list[dict]:
    """Build the generation request for one family, splice-style.

    The model receives ``prefix`` (imports, any helper function, the entry
    point's own signature) as read-only CONTEXT and ``body`` (the docstring's
    prose and examples, with the opening/closing quotes already cut off by
    :func:`split_spec`) as the only text it rewrites. It is never asked to
    reproduce anything in CONTEXT, so it cannot get that reproduction wrong --
    the family that most needs the exception, ``persona``, gets its own system
    prompt (:data:`_PERSONA_SYSTEM_PROMPT`) because its response has two parts.
    """
    system = _PERSONA_SYSTEM_PROMPT if family == "persona" else _SYSTEM_PROMPT
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": (
            f"{_FAMILY_INSTRUCTIONS[family]}\n\n"
            f"CONTEXT (for reference only -- do not reproduce):\n{prefix}\n\n"
            f"TEXT TO REWRITE:\n{body}"
        )},
    ]


def _parse_persona_response(raw: str) -> tuple[str, str]:
    """Split a persona-family response into ``(framing, body)`` at the sentinel.

    If the sentinel is missing, the whole response is treated as framing and the
    body is empty -- guessing which part is which would risk silently splicing
    framing text in as if it were the rewritten docstring. An empty body is
    caught downstream (Gate A rejects it as ``empty``), so nothing invalid is
    ever admitted; it is simply counted as a rejection instead of parsed wrong.
    """
    if _PERSONA_SENTINEL in raw:
        framing, _, body = raw.partition(_PERSONA_SENTINEL)
        return framing.strip("\n"), body
    return raw, ""


def _build_judge_messages(original: str, candidate: str) -> list[dict]:
    return [
        {"role": "system", "content": _JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"ORIGINAL SPECIFICATION:\n{original}\n\n"
            f"REWRITTEN SPECIFICATION:\n{candidate}"
        )},
    ]


# ---------------------------------------------------------------------------
# Gate A - structural invariants
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```[A-Za-z0-9_+-]*\s*(.*?)```", re.DOTALL)
_NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
_DEF_RE = re.compile(r"^[ \t]*(?:async[ \t]+)?def[ \t]+([A-Za-z_]\w*)", re.MULTILINE)


def strip_fence(raw: str) -> str:
    """Return the content of a markdown fence, if the model wrapped its answer."""
    fenced = _FENCE_RE.search(raw)
    return fenced.group(1) if fenced else raw


def signature_prefix(prompt: str, entry_point: str) -> str:
    """Everything up to and including the entry point's opening triple-quote.

    Anchored on the entry point's own ``def``, not on the first triple-quote in
    the prompt: 5 of 164 HumanEval tasks (e.g. ``HumanEval/32``) define a helper
    function — with its own docstring — before the entry point, and the first
    quote in the file belongs to that helper. Anchoring there would take the
    helper's docstring as "the signature", reject every otherwise-valid rewrite
    of those 5 tasks as `text_before_signature`, and never accept a single
    variant for them.

    Deliberately not ``paraphraser._split_docstring``: that helper *normalises*
    the split, appending a newline after the quote when the description starts on
    the same line (the common HumanEval shape, ``\"\"\" Check if ...``). A
    normalised prefix cannot be used as a byte-for-byte probe — it would never be
    found in a candidate, so every candidate would be rejected.
    """
    def_match = re.search(
        rf"^[ \t]*(?:async[ \t]+)?def[ \t]+{re.escape(entry_point)}\s*\(",
        prompt, re.MULTILINE,
    )
    search_from = def_match.start() if def_match else 0
    positions = [
        p for p in (prompt.find('"""', search_from), prompt.find("'''", search_from))
        if p != -1
    ]
    if not positions:
        return prompt
    return prompt[: min(positions) + 3]


def split_spec(prompt: str, entry_point: str) -> tuple[str, str, str]:
    """Split a prompt into ``(prefix, body, suffix)`` around its docstring.

    ``prefix`` is exactly :func:`signature_prefix` -- imports, any helper
    function in full, the entry point's own ``def`` line, and the opening
    triple-quote. ``suffix`` is the closing quote's own line onward (typically
    just four spaces, the closing quote, and a newline), taken from the
    *start of that line* rather than from the quote character itself, so
    ``body`` always ends cleanly after its last real content line with no
    dangling indentation for a rewrite to match.
    ``body`` -- everything between -- is the only part a rewrite ever touches.

    :func:`assemble` splices ``prefix`` and ``suffix`` back in byte-for-byte
    from the *original* prompt, so the model is never asked to reproduce them
    and cannot get that reproduction wrong. If no closing quote is found
    (a malformed prompt, never observed on real HumanEval data), ``suffix`` is
    empty and ``body`` is everything after ``prefix``.
    """
    prefix = signature_prefix(prompt, entry_point)
    quote = prefix[-3:] if prefix[-3:] in ('"""', "'''") else '"""'
    rest = prompt[len(prefix):]
    quote_idx = rest.rfind(quote)
    if quote_idx == -1:
        return prefix, rest, ""
    line_start = rest.rfind("\n", 0, quote_idx) + 1   # 0 if quote is on rest's first line
    return prefix, rest[:line_start], rest[line_start:]


def assemble(prefix: str, body: str, suffix: str, *, framing: str = "") -> str:
    """Reassemble a full prompt from a spliced prefix/suffix and a rewritten body.

    ``framing`` is the persona family's paragraph, placed before ``prefix``; every
    other family calls this with the default and gets exactly ``prefix + body +
    suffix``, so it can never smuggle in a preamble -- there is no code path for
    one. A ``body`` missing its trailing newline gets one added, so it never runs
    into ``suffix``'s closing-quote line on the same source line.
    """
    if body and not body.endswith("\n"):
        body += "\n"
    head = f"{framing.strip()}\n\n" if framing.strip() else ""
    return head + prefix + body + suffix


def _strip_leading_quote(line: str) -> str:
    """A rewrite that leads with the examples often opens the docstring right on
    one (``\"\"\" >>> f(1)``), so the quote comes off before the line is read."""
    stripped = line.strip()
    for quote in ('"""', "'''"):
        if stripped.startswith(quote):
            return stripped[3:].strip()
    return stripped


def _doctest_lines(text: str) -> list[str]:
    """Every ``>>>`` line plus its expected-output line.

    Exactly one following *non-blank* line is taken as the expected output.
    Across all 164 HumanEval prompts, 181 of the 182 doctest examples have a
    single-line expected output, and consuming until a blank line instead would
    swallow the prose that follows the examples once a rewrite puts them first —
    turning a legitimate reordering into a spurious ``examples_changed``
    rejection.

    Blank lines between the ``>>>`` and its output are skipped rather than read
    as "this example has no output". A rewrite that spaces its examples out is
    making a formatting change, not an example change, and the old behaviour
    scored it as the latter: the output line was dropped from the *candidate's*
    list only, so the comparison against the original failed and the candidate
    was rejected as ``examples_changed`` — the single most common Gate A
    rejection in the pilot. Verified to be a no-op on the reference side —
    extraction is byte-identical on all 164 original prompts with and without
    the skip — so this can only remove false rejections, never admit a real one.
    """
    lines = text.splitlines()
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = _strip_leading_quote(line)
        if not stripped.startswith(">>>"):
            continue
        out.append(stripped)
        j = i + 1
        while j < len(lines) and not _strip_leading_quote(lines[j]):
            j += 1
        following = _strip_leading_quote(lines[j]) if j < len(lines) else ""
        if following and not following.startswith(">>>") and following not in ('"""', "'''"):
            out.append(following)
    return out


def _normalize(text: str) -> str:
    """Collapse blank-line variance that carries no code meaning.

    Chat completions do not reliably reproduce blank-line counts: 45 of 164
    HumanEval prompts open with a blank line (tasks with no import statement),
    and PEP8-style spacing between top-level defs (a helper before the entry
    point) routinely comes back collapsed from two blank lines to one. Any run
    of blank lines, anywhere, collapses to exactly one. Shared between
    ``structural_gate``'s own comparisons and ``generate_family``'s duplicate
    tracking (``seen``), so both agree on what counts as "the same candidate".
    """
    return re.sub(r"\n{2,}", "\n\n", text.lstrip("\n"))


def _entry_body_code(tree: ast.AST, entry_point: str) -> list[str]:
    """The entry point's body statements, excluding its docstring.

    Returned as dumped AST so two prompts are compared by structure, not by
    formatting: rewording the docstring must not register as a code change, and
    reindenting an existing statement must not either.
    """
    node = next(
        (n for n in ast.walk(tree)
         if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
         and n.name == entry_point),
        None,
    )
    if node is None:
        return []
    return [
        ast.dump(stmt) for stmt in node.body
        if not (isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and isinstance(stmt.value.value, str))
    ]


def structural_gate(
    original: str,
    candidate: str,
    entry_point: str,
    family: str,
    *,
    seen: Optional[set[str]] = None,
) -> Optional[str]:
    """Return ``None`` if the candidate passes Gate A, else the rejection reason.

    Every check is a mechanical invariant that a meaning-preserving rewrite cannot
    violate, so no rejection here rests on a judgement call.
    """
    # See _normalize: collapses blank-line variance that carries no code
    # meaning, so a formatting difference alone cannot cause either a spurious
    # rejection or a missed no-op. ``seen`` is expected to already hold
    # normalised strings — generate_family stores them that way — so this
    # candidate must be normalised the same way before the membership check.
    original = _normalize(original)
    candidate = _normalize(candidate)

    if not candidate.strip():
        return "empty"

    if candidate == original:
        return "identical_to_original"

    if seen is not None and candidate in seen:
        return "duplicate_of_sibling"

    signature = signature_prefix(original, entry_point)
    if signature not in candidate:
        return "signature_not_verbatim"

    # The persona family frames the task before the code; every other family must
    # begin at the signature, so text in front of it is a smuggled instruction.
    preamble, _, body = candidate.partition(signature)
    if family != "persona" and preamble.strip():
        return "text_before_signature"

    code = signature + body
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return "does_not_parse"      # usually an unclosed docstring

    defined = set(_DEF_RE.findall(code))
    if entry_point not in defined:
        return "entry_point_missing"
    if defined - set(_DEF_RE.findall(original)):
        return "extra_def_introduced"

    # The prompt is a specification, and it stops at the docstring. A rewrite
    # that also implements the function would hand the answer to the model under
    # test, so that (task, relation) cell would measure nothing.
    #
    # Compared against the original's own body rather than against "a docstring
    # and nothing else": HumanEval/115 puts `import math` inside the function
    # ahead of its docstring, so a fixed rule would reject every rewrite of that
    # task forever and silently starve it of variants.
    if _entry_body_code(tree, entry_point) != _entry_body_code(
        ast.parse(original), entry_point
    ):
        return "function_body_written"

    original_examples = _doctest_lines(original)
    candidate_examples = _doctest_lines(candidate)
    if family == "reorder":
        # Presenting the examples first is the point of this family, so their
        # order is free.  Their content is not.
        if sorted(original_examples) != sorted(candidate_examples):
            return "examples_changed"
    elif original_examples != candidate_examples:
        return "examples_changed"

    new_numbers = set(_NUMBER_RE.findall(candidate)) - set(_NUMBER_RE.findall(original))
    if new_numbers:
        return "new_numeric_literal:" + ",".join(sorted(new_numbers))

    return None


# ---------------------------------------------------------------------------
# Gate B - held-out judge
# ---------------------------------------------------------------------------

async def judge_candidate(
    original: str,
    candidate: str,
    judge_model: str,
    client: InnkubeClient,
) -> tuple[str, str]:
    """Return ``(verdict, reason)`` from the held-out judge model.

    A judge that fails to answer is reported as UNSURE, i.e. the candidate is
    rejected.  Admitting an unvalidated variant because the validator broke would
    put unchecked prompts into the corpus, which is the one outcome the gate
    exists to prevent.
    """
    try:
        replies = await client.complete(
            model=judge_model,
            messages=_build_judge_messages(original, candidate),
            temperature=0.0,
            max_tokens=JUDGE_MAX_TOKENS,
            n=1,
        )
    except Exception as exc:
        return "UNSURE", f"judge call failed: {type(exc).__name__}: {exc}"

    if not replies or not replies[0].strip():
        return "UNSURE", "judge returned nothing"

    lines = [ln.strip() for ln in replies[0].strip().splitlines() if ln.strip()]
    head = lines[0].upper()
    # NOT_EQUIVALENT is checked first: it has EQUIVALENT as a suffix, so a
    # startswith scan in declaration order would still be safe, but ordering the
    # test explicitly keeps it safe if the tuple is ever reordered.
    verdict = next(
        (v for v in ("NOT_EQUIVALENT", "EQUIVALENT", "UNSURE") if head.startswith(v)),
        None,
    )
    if verdict is None:
        return "UNSURE", f"unparseable verdict: {lines[0][:120]}"
    return verdict, lines[1][:300] if len(lines) > 1 else ""


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def variant_id(family: str, index: int) -> str:
    """``llm_lexical_01`` - slots straight into the existing relation string key."""
    return f"llm_{family}_{index:02d}"


async def generate_family(
    task: HumanEvalTask,
    family: str,
    generator_model: str,
    judge_model: str,
    client: InnkubeClient,
    *,
    n_per_family: int = N_PER_FAMILY,
    seen: Optional[set[str]] = None,
) -> tuple[list[dict], list[dict]]:
    """Generate up to ``n_per_family`` validated variants of one task's prompt.

    Returns ``(accepted, rejected)``.  Accepted entries carry their own validation
    record and rejected ones carry the reason, so the rejection rate is a
    reportable statistic rather than an invisible one.
    """
    accepted: list[dict] = []
    rejected: list[dict] = []
    seen = set() if seen is None else seen
    prefix, body, suffix = split_spec(task.prompt, task.entry_point)

    for attempt in range(1, MAX_REGEN + 1):
        if len(accepted) >= n_per_family:
            break
        try:
            raw_candidates = await client.complete(
                model=generator_model,
                messages=_build_generation_messages(prefix, body, family),
                temperature=GENERATION_TEMPERATURE,
                max_tokens=GENERATION_MAX_TOKENS,
                n=n_per_family + 2,
                cache_salt=f"paraphrase-attempt-{attempt}",
            )
        except Exception as exc:
            logger.warning("Generation call failed for %s/%s attempt %d: %s",
                           task.task_id, family, attempt, exc)
            rejected.append({"family": family, "attempt": attempt, "gate": "call",
                             "reason": f"call_failed:{type(exc).__name__}"})
            continue

        for raw in raw_candidates:
            if len(accepted) >= n_per_family:
                break
            raw_clean = strip_fence(raw).strip("\n")

            if family == "persona":
                framing, rewritten_body = _parse_persona_response(raw_clean)
                candidate = assemble(prefix, rewritten_body, suffix, framing=framing)
            else:
                candidate = assemble(prefix, raw_clean, suffix)

            reason = structural_gate(task.prompt, candidate, task.entry_point,
                                     family, seen=seen)
            if reason is not None:
                rejected.append({"family": family, "attempt": attempt,
                                 "gate": "structural", "reason": reason})
                continue

            verdict, judge_reason = await judge_candidate(
                task.prompt, candidate, judge_model, client
            )
            if verdict != "EQUIVALENT":
                rejected.append({"family": family, "attempt": attempt,
                                 "gate": "judge", "reason": verdict,
                                 "judge_reason": judge_reason})
                continue

            seen.add(_normalize(candidate))
            accepted.append({
                "variant_id": variant_id(family, len(accepted) + 1),
                "family": family,
                "text": candidate,
                "validation": {
                    "structural": "pass",
                    "judge_verdict": verdict,
                    "judge_model": judge_model,
                    "judge_reason": judge_reason,
                    "n_regen_attempts": attempt,
                },
            })

    if len(accepted) < n_per_family:
        logger.warning(
            "%s/%s: only %d/%d variants survived validation after %d attempts",
            task.task_id, family, len(accepted), n_per_family, MAX_REGEN,
        )
    return accepted, rejected


async def generate_task_variants(
    task: HumanEvalTask,
    generator_model: str,
    judge_model: str,
    client: InnkubeClient,
    *,
    families: Optional[list[str]] = None,
    n_per_family: int = N_PER_FAMILY,
) -> tuple[dict, list[dict], list[dict]]:
    """Generate every family for one task.

    Returns ``(task_entry, gaps, rejections)``.  A family that could not be filled
    appears in ``gaps`` and simply has fewer variants; it is never padded.
    """
    families = families or FAMILIES
    variants: list[dict] = []
    gaps: list[dict] = []
    rejections: list[dict] = []
    seen: set[str] = set()

    for family in families:
        accepted, rejected = await generate_family(
            task, family, generator_model, judge_model, client,
            n_per_family=n_per_family, seen=seen,
        )
        variants.extend(accepted)
        rejections.extend({**r, "task_id": task.task_id} for r in rejected)
        if len(accepted) < n_per_family:
            gaps.append({
                "task_id": task.task_id, "family": family,
                "filled": len(accepted), "requested": n_per_family,
            })

    return {"original": task.prompt, "variants": variants}, gaps, rejections


# ---------------------------------------------------------------------------
# Corpus file: read, hash, verify
# ---------------------------------------------------------------------------

class CorpusError(RuntimeError):
    """The paraphrase corpus is missing, malformed, or does not match its hash."""


_CACHE: dict[tuple[str, float], dict] = {}


def tasks_sha256(corpus: dict) -> str:
    """SHA-256 of the ``tasks`` block - the payload, excluding the manifest."""
    blob = json.dumps(corpus["tasks"], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def load_corpus(path: str | Path) -> dict:
    """Read and cache the corpus file.  Cached on (resolved path, mtime)."""
    p = Path(path)
    try:
        stat = p.stat()
    except OSError as exc:
        raise CorpusError(
            f"paraphrase corpus not found at {p} - generate it with:\n"
            f"       .venv/bin/python scripts/generate_paraphrases.py"
        ) from exc

    cache_key = (str(p.resolve()), stat.st_mtime)
    if cache_key not in _CACHE:
        try:
            corpus = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CorpusError(f"paraphrase corpus at {p} is not valid JSON: {exc}") from exc
        if "tasks" not in corpus or "manifest" not in corpus:
            raise CorpusError(f"paraphrase corpus at {p} has no 'manifest'/'tasks' block")
        _CACHE.clear()      # only ever one corpus in play; keep this bounded
        _CACHE[cache_key] = corpus
    return _CACHE[cache_key]


def verify_corpus(corpus: dict, expected_sha256: Optional[str], path: str | Path) -> None:
    """Abort if the corpus does not match the SHA pinned in the config.

    Silent regeneration is exactly the confound this design exists to prevent:
    every model in the comparison must see the same prompts, and a corpus that
    drifted between two models' runs makes their scores incomparable.
    """
    actual = tasks_sha256(corpus)
    stated = corpus.get("manifest", {}).get("sha256")
    if stated and stated != actual:
        raise CorpusError(
            f"{path}: contents do not match the sha256 in its own manifest "
            f"(manifest={stated[:12]}..., actual={actual[:12]}...). The file has been "
            "edited by hand since it was generated."
        )
    if expected_sha256 and expected_sha256 != actual:
        raise CorpusError(
            f"{path}: sha256 {actual[:12]}... does not match rq2.corpus_sha256 "
            f"{expected_sha256[:12]}... in the config. Completions already generated "
            "used the pinned corpus; either restore that corpus or update "
            "rq2.corpus_sha256 and re-run RQ2 generate with --force."
        )


def corpus_variant_ids(corpus: dict) -> list[str]:
    """Every variant id the corpus declares, in stable family-then-index order.

    Read from the manifest rather than by scanning tasks, so one task's generation
    gap does not shorten the relation list for every other task.  A task missing a
    variant leaves that (task, relation) cell absent, which ``rq2/ranking.py``
    already records as incomplete rather than scoring 0.0.
    """
    manifest = corpus.get("manifest", {})
    families = manifest.get("families", FAMILIES)
    n = manifest.get("n_per_family", N_PER_FAMILY)
    return [variant_id(f, i) for f in families for i in range(1, n + 1)]


def family_of(relation: str) -> Optional[str]:
    """``llm_lexical_02`` -> ``lexical``; ``None`` for non-corpus relations."""
    if not relation.startswith("llm_"):
        return None
    parts = relation.split("_")
    return "_".join(parts[1:-1]) if len(parts) >= 3 else None


def variants_for_task(corpus: dict, task_id: str) -> dict[str, str]:
    """``{variant_id: prompt_text}`` for one task; empty if the task is absent."""
    entry = corpus.get("tasks", {}).get(task_id)
    if not entry:
        return {}
    return {v["variant_id"]: v["text"] for v in entry.get("variants", [])}
