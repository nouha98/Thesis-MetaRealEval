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

Validation
----------
Gate A (:func:`structural_gate`) — mechanical, free, runs first.  Rejects a
candidate that moved the signature, dropped an example, invented a number, does
not parse, duplicates a sibling, or is byte-identical to the original.  That last
one is the defect above, asserted rather than assumed.

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
PROMPT_TEMPLATE_VERSION = 1

FAMILIES = ["lexical", "reorder", "formal", "persona", "terse"]
N_PER_FAMILY = 3

# Mirrors the RQ1 mutant-generation retry budget.  Each attempt re-requests the
# whole family; without a cache_salt the second attempt would replay the first
# attempt's cached completions verbatim and the budget would buy nothing.
MAX_REGEN = 4

JUDGE_VERDICTS = ("EQUIVALENT", "NOT_EQUIVALENT", "UNSURE")


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You rewrite Python task specifications. The input is a HumanEval-style prompt: "
    "optional imports, a function signature, and a docstring holding the specification "
    "and doctest examples. There is no function body and you must not write one.\n\n"
    "Return ONLY the rewritten prompt. No markdown fences, no commentary, no body.\n\n"
    "Hard invariants - breaking any one makes your output unusable:\n"
    "- Reproduce the import lines, the def line, and the opening triple-quote EXACTLY, "
    "byte for byte, and close the docstring.\n"
    "- Reproduce every >>> line and every expected-output line EXACTLY, character for "
    "character. Do not add examples and do not drop any.\n"
    "- Do not add, remove, weaken, or strengthen a single requirement. The set of inputs "
    "accepted and the outputs produced must be identical.\n"
    "- Do not introduce any number that does not already appear in the original.\n"
    "- Do not rename the function or its parameters, and do not introduce another def."
)

_FAMILY_INSTRUCTIONS = {
    "lexical": (
        "Rewrite the docstring prose using different vocabulary and different sentence "
        "structure while preserving the exact programming requirements. Substitute "
        "synonyms and recast phrasings; do not merely reorder the existing words."
    ),
    "reorder": (
        "Rewrite the docstring so its information arrives in a different order: put the "
        "examples before the prose description, and where the description has several "
        "clauses or constraints, present them in a different sequence. The wording of "
        "each individual requirement may stay close to the original; what must change is "
        "the order in which the reader meets them."
    ),
    "formal": (
        "Rewrite the docstring in a formal specification register: passive or impersonal "
        "voice, precise technical terms, requirements stated as explicit conditions on "
        "inputs and outputs. It should read like a written standard rather than an "
        "informal note to a colleague."
    ),
    "persona": (
        "Prepend a short framing paragraph addressed to the implementer - casting them in "
        "a role, or setting a scenario in which this function is needed - then reproduce "
        "the signature and give the docstring in a voice that matches that framing. The "
        "framing paragraph goes BEFORE the import lines and the def line; everything from "
        "the def line onward must still satisfy the hard invariants."
    ),
    "terse": (
        "Rewrite the docstring as tersely as possible: strip every word that does not "
        "carry a requirement, prefer clipped noun phrases over full sentences, and drop "
        "hedging and pleasantries. Every constraint present in the original must survive "
        "the compression - terse, not incomplete."
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


def _build_generation_messages(prompt: str, family: str) -> list[dict]:
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": (
            f"{_FAMILY_INSTRUCTIONS[family]}\n\n"
            f"Rewrite this specification:\n\n{prompt}"
        )},
    ]


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


def signature_prefix(prompt: str) -> str:
    """Everything up to and including the opening triple-quote, verbatim.

    Deliberately not ``paraphraser._split_docstring``: that helper *normalises*
    the split, appending a newline after the quote when the description starts on
    the same line (which is the common HumanEval shape, ``\"\"\" Check if ...``).
    A normalised prefix cannot be used as a byte-for-byte probe — it would never
    be found in a candidate, so every candidate would be rejected.
    """
    positions = [p for p in (prompt.find('"""'), prompt.find("'''")) if p != -1]
    if not positions:
        return prompt
    return prompt[: min(positions) + 3]


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

    Exactly one following line is taken as the expected output. Across all 164
    HumanEval prompts, 181 of the 182 doctest examples have a single-line
    expected output, and consuming until a blank line instead would swallow the
    prose that follows the examples once a rewrite puts them first — turning a
    legitimate reordering into a spurious ``examples_changed`` rejection.
    """
    lines = text.splitlines()
    out: list[str] = []
    for i, line in enumerate(lines):
        stripped = _strip_leading_quote(line)
        if not stripped.startswith(">>>"):
            continue
        out.append(stripped)
        following = _strip_leading_quote(lines[i + 1]) if i + 1 < len(lines) else ""
        if following and not following.startswith(">>>") and following not in ('"""', "'''"):
            out.append(following)
    return out


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
    if not candidate.strip():
        return "empty"

    if candidate == original:
        return "identical_to_original"

    if seen is not None and candidate in seen:
        return "duplicate_of_sibling"

    signature = signature_prefix(original)
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
            max_tokens=256,
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

    for attempt in range(1, MAX_REGEN + 1):
        if len(accepted) >= n_per_family:
            break
        try:
            raw_candidates = await client.complete(
                model=generator_model,
                messages=_build_generation_messages(task.prompt, family),
                temperature=0.7,
                max_tokens=1024,
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
            candidate = strip_fence(raw).strip("\n")
            if candidate:
                candidate += "\n"

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

            seen.add(candidate)
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
