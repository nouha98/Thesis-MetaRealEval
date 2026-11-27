"""A3: the bounded test agent (plan rev. 9.3, Stage 4; decisions 7 and 10.3).

Per target (a surviving discovery fault group of one development task) one model writes ONE pytest
test that checks a property the docstring states, passes on the reference, and fails on the fault.
The loop is propose -> check -> feedback -> repair, with at most ``attempts`` proposals; the
feedback is the first failed check's reason (no separate category machinery, plan rev. 9.3).

Checks, in order (each failure is the feedback for the next attempt):
  1. ``syntax``           one ```python block defining ``def test_a3():``, compiles;
  2. ``forbidden_import`` only ``pytest`` and ``math`` may be imported (the module is imported for it);
  3. ``private_access``   no ``_name`` attribute (dunders are allowed), no ``getattr(x, "_...")``;
  4. ``non_api``          no ``repr(``, ``vars(``, ``__dict__``, ``__class__``, ``__module__``,
                          ``__qualname__``, ``__name__`` (implementation details, decisions 10.2);
  5. ``no_doc_quote``     every ``assert`` / ``pytest.raises`` is preceded by a ``# doc: "..."`` comment
                          quoting the docstring words it relies on (so the audit can judge it);
  6. ``reference_fails``  passes on the reference 3 times and alone (``admission.admit``);
  7. ``fault_not_detected`` fails on the target fault.
Contract-valid inputs cannot be checked statically for free-form code: the prompt gives the domain,
and validity is judged in the audit (decisions 7, condition 1).

A3 v2 (decisions 10.6) changes one thing: no access to reference behaviour. Its prompt omits the reference
implementation (the fault diff has no context lines), and its reference-failure feedback is value-free: the
status, the exception type and the failing line of the test, never a value or pytest output. Everything else
is v1's (``first_prompt``, ``check`` and the repair message are pinned by a test, byte for byte).
"""

from __future__ import annotations

import ast
import asyncio
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

from ..benchmarks.outcomes import ORDINARY_PASS, classify_run, static_test_info
from ..benchmarks.witness import GEN_ALIAS
from ..core.sandbox import execute_pytest
from .admission import admit

ALLOWED_IMPORTS = {"pytest", "math"}
NON_API = ("repr(", "vars(", "__dict__", "__class__", "__module__", "__qualname__", "__name__")
TEST_NAME = "test_a3"

SYSTEM = ("You write one pytest test for a Python class. The test must check only behaviour that the "
          "class's docstrings state. Answer with exactly one ```python code block.")

RULES = f"""Rules for the test:
- Define exactly one function `def {TEST_NAME}():`. The module is already imported as `{GEN_ALIAS}`
  (use `{GEN_ALIAS}.<ClassName>`). You may also `import pytest` or `import math`; nothing else.
- Use only the public interface shown in the skeleton: no attribute or method whose name starts with `_`
  (dunder methods such as `__call__` or `__len__` are allowed through normal syntax: `obj(x)`, `len(obj)`).
- Do not inspect implementation details: no `repr(`, `vars(`, `__dict__`, `__class__`, `__name__`.
- Use only inputs inside the documented domain below.
- Every assertion (`assert ...` or `with pytest.raises(...)`) must check a property the DOCSTRING states,
  never a detail that only the reference implementation shows. Put a comment directly above each one:
  `# doc: "<the docstring words it relies on>"`.
- The test must pass on the reference implementation and fail on the faulty version.
- Deterministic: no randomness, time, files, network or environment."""


def domain_text(contract: dict) -> str:
    """The reviewed contract's input domain, as plain lines for the prompt."""
    def params(ps):
        out = []
        for p in ps:
            if not p.get("generate", True):
                continue
            c = {k: v for k, v in (p.get("constraints") or {}).items() if v not in (None, [], {})}
            t = (p.get("type") or {}).get("t", "?")
            out.append(f"{p['name']}: {t}" + (f" {c}" if c else "") + (" (optional)" if p.get("has_default") else ""))
        return ", ".join(out) or "(none)"
    lines = [f"- constructor {contract['class_name']}({params(contract['constructor']['params'])})"]
    for name, m in sorted(contract.get("methods", {}).items()):
        if m.get("generate", True):
            lines.append(f"- {name}({params(m.get('params', []))})")
    return "\n".join(lines)


def first_prompt(skeleton: str, contract: dict, reference: str, fault_diff: str) -> list[dict]:
    user = (f"Class skeleton with its docstrings (the specification):\n```python\n{skeleton.strip()}\n```\n\n"
            f"Documented input domain (use only these inputs):\n{domain_text(contract)}\n\n"
            f"Reference implementation (correct; the test must pass on it):\n```python\n{reference.strip()}\n```\n\n"
            f"A faulty version differs from the reference like this:\n```diff\n{fault_diff.strip()}\n```\n\n"
            f"Write a test that fails on the faulty version because it breaks something the docstring states. "
            f"If the fault only changes behaviour the docstring leaves open, still write the best docstring-based "
            f"test you can; it will simply not be admitted.\n\n{RULES}")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


def extract_code(text: str) -> Optional[str]:
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "", flags=re.S)
    return blocks[-1].strip() + "\n" if blocks else None


def static_check(code: Optional[str]) -> Optional[tuple[str, str]]:
    """(check, message) for the first static failure, or None."""
    if not code:
        return "syntax", "no ```python code block found"
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return "syntax", f"SyntaxError: {exc}"
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    if [f.name for f in fns] != [TEST_NAME]:
        return "syntax", f"define exactly one top-level function `{TEST_NAME}` (found {[f.name for f in fns]})"
    other = [n for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.Import, ast.ImportFrom))]
    if other:
        return "syntax", "only imports and the test function may appear at top level (put helpers inside the test)"
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            mods = [a.name.split(".")[0] for a in n.names] if isinstance(n, ast.Import) else [(n.module or "").split(".")[0]]
            bad = [m for m in mods if m not in ALLOWED_IMPORTS]
            if bad:
                return "forbidden_import", f"import of {bad} is not allowed (only pytest, math)"
        if isinstance(n, ast.Attribute) and n.attr.startswith("_") and not (n.attr.startswith("__") and n.attr.endswith("__")):
            return "private_access", f"private attribute `{n.attr}` is not part of the public interface"
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in ("getattr", "setattr", "hasattr")
                and len(n.args) > 1 and isinstance(n.args[1], ast.Constant) and str(n.args[1].value).startswith("_")):
            return "private_access", f"{n.func.id}(..., {n.args[1].value!r}) reaches a private name"
    for tok in NON_API:
        if tok in code:
            return "non_api", f"`{tok}` inspects an implementation detail, not documented behaviour"
    lines = code.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("assert ") or s.startswith("with pytest.raises"):
            prev = next((lines[j].strip() for j in range(i - 1, -1, -1) if lines[j].strip()), "")
            if not prev.startswith("# doc:"):
                return "no_doc_quote", f"line {i + 1} (`{s[:60]}`) has no `# doc: \"...\"` comment directly above it"
    return None


def _run(module: str, code: str, test_code: str, timeout_s: float) -> tuple[str, str]:
    run = execute_pytest(module, code, test_code, timeout_s=timeout_s, select=[TEST_NAME])
    res = classify_run(run, static_test_info(test_code), requested=[TEST_NAME])
    out = res[TEST_NAME].outcome if TEST_NAME in res else "missing"
    tail = "\n".join((run.stdout or "").splitlines()[-25:])
    return out, tail


def test_file(module: str, body: str) -> str:
    return f"import {module} as {GEN_ALIAS}\n\n{body}"


def check(module: str, reference: str, fault: str, body: str, timeout_s: float) -> dict:
    """Run every check on one proposal; {"admitted", "check", "message"}."""
    st = static_check(body)
    if st:
        return {"admitted": False, "check": st[0], "message": st[1]}
    code = test_file(module, body)
    adm = admit(module, reference, code, [TEST_NAME], timeout_s, repeats=3)[TEST_NAME]
    if not adm["admitted"]:
        _, tail = _run(module, reference, code, timeout_s)
        return {"admitted": False, "check": "reference_fails",
                "message": f"the test does not pass on the reference ({adm['reason']}; outcomes {adm['together']}, "
                           f"alone {adm['alone']}). pytest output:\n{tail}"}
    out, _ = _run(module, fault, code, timeout_s)
    if out == ORDINARY_PASS:
        return {"admitted": False, "check": "fault_not_detected",
                "message": "the test passes on the faulty version too: it does not detect the fault"}
    return {"admitted": True, "check": None, "message": None, "fault_outcome": out}


# --- A3 v2 (decisions 10.6) ------------------------------------------------------------------------

def first_prompt_v2(skeleton: str, contract: dict, fault_diff: str) -> list[dict]:
    """v1's prompt without the reference implementation (the diff is given without context lines)."""
    user = (f"Class skeleton with its docstrings (the specification):\n```python\n{skeleton.strip()}\n```\n\n"
            f"Documented input domain (use only these inputs):\n{domain_text(contract)}\n\n"
            f"A faulty version differs from the reference like this:\n```diff\n{fault_diff.strip()}\n```\n\n"
            f"Write a test that fails on the faulty version because it breaks something the docstring states. "
            f"If the fault only changes behaviour the docstring leaves open, still write the best docstring-based "
            f"test you can; it will simply not be admitted.\n\n{RULES}")
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


DIAG_NAME = "test_a3_diag"
_DIAG = f"""


def {DIAG_NAME}():
    import os as _d_os, traceback as _d_tb
    try:
        {TEST_NAME}()
    except BaseException as _d_exc:
        _d_fr = [f for f in _d_tb.extract_tb(_d_exc.__traceback__)
                 if _d_os.path.basename(f.filename) == _d_os.path.basename(__file__)]
        print("A3DIAG", type(_d_exc).__name__, _d_fr[-1].lineno if _d_fr else 0)
        raise
"""
_HEADER_LINES = 2                      # ``test_file``: the import line and a blank line precede the body


def reference_failure_v2(module: str, reference: str, body: str, timeout_s: float) -> str:
    """Value-free feedback for a test that fails on the reference: the exception type and the test's own failing
    line only (no value, no message, no pytest output, no line of the reference)."""
    run = execute_pytest(module, reference, test_file(module, body) + _DIAG, timeout_s=timeout_s, select=[DIAG_NAME])
    m = re.search(r"^A3DIAG (\w+) (\d+)\r?$", run.stdout or "", flags=re.M)
    msg = "the test fails on a correct implementation"
    if m:
        lines, n = body.splitlines(), int(m.group(2)) - _HEADER_LINES
        where = f" at line {n} of the test: `{lines[n - 1].strip()}`" if 1 <= n <= len(lines) else ""
        msg += f" ({m.group(1)} raised{where})"
    return msg


def check_v2(module: str, reference: str, fault: str, body: str, timeout_s: float) -> dict:
    """``check`` with value-free reference-failure feedback; the other checks and their messages are v1's."""
    st = static_check(body)
    if st:
        return {"admitted": False, "check": st[0], "message": st[1]}
    code = test_file(module, body)
    adm = admit(module, reference, code, [TEST_NAME], timeout_s, repeats=3)[TEST_NAME]
    if not adm["admitted"]:
        return {"admitted": False, "check": "reference_fails",
                "message": reference_failure_v2(module, reference, body, timeout_s)}
    out, _ = _run(module, fault, code, timeout_s)
    if out == ORDINARY_PASS:
        return {"admitted": False, "check": "fault_not_detected",
                "message": "the test passes on the faulty version too: it does not detect the fault"}
    return {"admitted": True, "check": None, "message": None, "fault_outcome": out}


@dataclass
class TargetResult:
    attempts: list[dict] = field(default_factory=list)
    admitted: Optional[str] = None


async def run_target(ask: Callable[[list[dict], int], Awaitable[tuple[str, dict]]], messages: list[dict],
                     module: str, reference: str, fault: str, timeout_s: float, attempts: int = 3,
                     checker: Optional[Callable[..., dict]] = None) -> TargetResult:
    """The bounded loop. ``await ask(messages, attempt) -> (answer text, call meta)``; the checks run in a
    worker thread so several targets can wait on the model at once. ``checker``: ``check`` (v1, the default)
    or ``check_v2``; the repair message is the same for both."""
    res = TargetResult()
    msgs = list(messages)
    for k in range(attempts):
        text, meta = await ask(msgs, k)
        body = extract_code(text)
        verdict = (await asyncio.to_thread(checker or check, module, reference, fault, body, timeout_s)) if body else \
            {"admitted": False, "check": "syntax", "message": "no ```python code block found"}
        res.attempts.append({"attempt": k, "code": body, "verdict": verdict, "meta": meta})
        if verdict["admitted"]:
            res.admitted = body
            break
        msgs = msgs + [{"role": "assistant", "content": text or ""},
                       {"role": "user", "content": f"The test was not admitted. Check `{verdict['check']}`: "
                                                   f"{verdict['message']}\nFix it and answer with one ```python block. "
                                                   f"The rules above still apply."}]
    return res
