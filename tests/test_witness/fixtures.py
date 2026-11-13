"""A synthetic stateful class, its skeleton, P tests and one mutant per Gate G2 case."""

import re

from meta_real_eval.benchmarks.base import Task

MODULE = "counter_mod"

REFERENCE = '''
class Counter:
    """A counter.

    Attributes:
        count (int): the current value.
    """

    def __init__(self, start: int = 0):
        """Start the counter.

        Args:
            start (int): initial value.
        """
        self.count = start
        self._history = []

    def add(self, n: int) -> int:
        """Add n and return the new count.

        Args:
            n (int): amount to add.

        Raises:
            ValueError: if n is negative.
        """
        if n < 0:
            raise ValueError("negative")
        self._history.append(n)
        self.count += n
        return self.count

    def half(self) -> float:
        """Return half of the count."""
        return self.count / 2

    def ratio(self, d: int) -> float:
        """Return the count divided by d.

        Args:
            d (int): divisor.
        """
        return self.count / d
'''

TESTS = f'''import pytest
import {MODULE} as module_0

def test_case_0():
    counter_0 = module_0.Counter(1)
    var_0 = counter_0.add(2)
    assert var_0 == 3

def test_case_1():
    counter_0 = module_0.Counter()
    var_0 = counter_0.half()
    assert var_0 == 0.0
    assert counter_0._history == []

def test_case_2():
    counter_0 = module_0.Counter(4)
    var_0 = counter_0.ratio(2)
    assert var_0 == 2.0

@pytest.mark.xfail(strict=True)
def test_case_3():
    counter_0 = module_0.Counter(4)
    var_0 = counter_0.ratio(0)
'''


def skeleton(src: str = REFERENCE) -> str:
    """Bodies replaced by `pass`, docstrings kept (the RealClassEval skeleton shape)."""
    out, lines, i = [], src.splitlines(), 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        if line.strip().startswith("def "):
            j = i + 1
            if lines[j].strip().startswith('"""'):
                while True:
                    out.append(lines[j])
                    if lines[j].strip().endswith('"""') and (j > i + 1 or lines[j].strip().count('"""') == 2):
                        break
                    j += 1
                j += 1
            indent = re.match(r"\s*", line).group(0) + "    "
            out.append(indent + "pass")
            while j < len(lines) and (not lines[j].strip() or lines[j].startswith(indent)):
                j += 1
            i = j
            continue
        i += 1
    return "\n".join(out)


def make_task(reference: str = REFERENCE, tests: str = TESTS) -> Task:
    return Task(task_id="Fixture/counter", task_index=0, label="FIX_counter", split="csn",
                prompt=skeleton(reference), reference_code=reference, test_code=tests,
                target="Counter", module_name=MODULE, meta={}, raw={})


DEPENDENCY_SCAN = {"tasks": {"Fixture/counter": {"stdlib_only": True}}}


def mutate(old: str, new: str) -> str:
    assert old in REFERENCE, old
    return REFERENCE.replace(old, new, 1)


MUTANTS = {
    # state-dependent fault: invisible to the P tests (counts stay below 5)
    "state_fault": mutate("        self.count += n\n", "        if self.count < 5:\n            self.count += n\n"),
    # private state only: history duplicated, no public observation changes
    "private_only": mutate("        self._history.append(n)\n", "        self._history.append(n)\n        self._history.append(n)\n"),
    # mutant-only exception on a valid input
    "mutant_exception": mutate("        return self.count / 2\n",
                               "        if self.count > 3:\n            raise RuntimeError('boom')\n        return self.count / 2\n"),
    # differs only where the reference raises an undocumented exception (d == 0)
    "uncertain_only": mutate("        return self.count / d\n", "        return self.count / d if d else 0.0\n"),
    # hangs where the reference returns
    "nontermination": mutate("        return self.count / 2\n",
                             "        while self.count > 7:\n            pass\n        return self.count / 2\n"),
    # behaviourally equivalent on the public contract
    "equivalent": mutate("        return self.count / 2\n", "        return self.count / 2.0\n"),
    # does not import
    "invalid": REFERENCE.replace("class Counter:", "class Counter(:", 1),
}
