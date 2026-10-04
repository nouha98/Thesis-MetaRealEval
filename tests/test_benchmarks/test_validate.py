"""M0 gate tests: validate_task on synthetic tasks, one per exclusion path,
plus the D2 classes that only appear on a real reference run."""

from __future__ import annotations

from meta_real_eval.benchmarks.base import Task
from meta_real_eval.benchmarks.validate import skeleton_baseline, validate_task

MODULE = "snippet_9"

REFERENCE = '''\
import random


class Bag:
    registry = []

    def __init__(self, n=0):
        self.n = n

    def add(self, k):
        if k < 0:
            raise ValueError("negative")
        self.n += k
        return self.n

    def remember(self):
        Bag.registry.append(self.n)
        return len(Bag.registry)

    def draw(self):
        return random.random()
'''

SKELETON = '''\
class Bag:

    def __init__(self, n: "random.Random" = 0):
        pass

    def add(self, k):
        pass

    def remember(self):
        pass

    def draw(self):
        pass
'''

TESTS = '''\
import pytest
import inspect as module_1
import snippet_9 as module_0


def test_behavioural():
    bag_0 = module_0.Bag(1)
    var_0 = bag_0.add(2)
    assert var_0 == 3


def test_explicit_raises():
    bag_0 = module_0.Bag(1)
    with pytest.raises(ValueError):
        bag_0.add(-1)


@pytest.mark.xfail(strict=True)
def test_generic_xfail():
    bag_0 = module_0.Bag(1)
    bag_0.add('x')


def test_constructor_only():
    module_0.Bag(5)


def test_reference_mismatch():
    bag_0 = module_0.Bag(1)
    var_0 = bag_0.add(1)
    assert var_0 == 99


def test_order_a():
    bag_0 = module_0.Bag(1)
    var_0 = bag_0.remember()
    assert var_0 == 1


def test_order_b():
    bag_0 = module_0.Bag(2)
    var_0 = bag_0.remember()
    assert var_0 == 2


def test_nondeterministic():
    bag_0 = module_0.Bag(0)
    var_0 = bag_0.draw()
    assert var_0 == 0.5


def test_env_only():
    bag_0 = module_0.Bag(0)
    assert module_1.CO_NESTED == 16


def test_env_mixed():
    bag_0 = module_0.Bag(4)
    assert bag_0.n == 4
    assert module_1.CO_NESTED == 16
'''


def _task(**over) -> Task:
    fields = dict(task_id=f"RealClassEval/csn/{MODULE}", task_index=0, label=f"RCE_csn_{MODULE}",
                  prompt=SKELETON, reference_code=REFERENCE, test_code=TESTS, target="Bag",
                  split="csn", module_name=MODULE, raw={"metrics": {"SumCyclomatic": 3.0}})
    fields.update(over)
    return Task(**fields)


def _validate(task):
    return validate_task(task, suite_timeout_s=30, scenario_timeout_s=10, seed=42, pool_sizes=(20,))


def test_full_d2_classification_on_a_real_reference_run():
    rec = _validate(_task())
    assert rec["status"] == "accepted"
    v = {name: t["validity"] for name, t in rec["tests"].items()}
    assert v["test_behavioural"] == "valid_behavioural"
    assert v["test_explicit_raises"] == "valid_exception_oracle"
    assert v["test_generic_xfail"] == "valid_exception_oracle"
    assert v["test_constructor_only"] == "valid_behavioural"
    assert v["test_reference_mismatch"] == "invalid_reference_mismatch"
    # registry is a class attribute: test_order_b only sees 2 entries after
    # test_order_a ran in the same process.
    assert v["test_order_a"] == "valid_behavioural"
    assert v["test_order_b"] == "invalid_order_dependent"
    # random.random() never equals 0.5, so this is a stable *mismatch*, not
    # flakiness -- the nondeterminism shows up in the scenario mask instead.
    assert v["test_nondeterministic"] == "invalid_reference_mismatch"
    assert v["test_env_only"] == "invalid_environment_assertion"
    assert v["test_env_mixed"] == "valid_behavioural"


def test_exception_oracle_provenance_and_types():
    t = _validate(_task())["tests"]
    assert t["test_explicit_raises"]["source"] == "explicit_pytest_raises"
    assert t["test_generic_xfail"]["source"] == "reference_xfail"
    assert t["test_generic_xfail"]["ref_exc_type"] == "builtins.TypeError"


def test_trivial_uses_an_importable_skeleton_baseline():
    """SKELETON's signature references `random` without importing it (like the
    real corpus); the baseline prepends the reference's imports so it can be
    imported, and the constructor-only test is then trivial."""
    assert skeleton_baseline(_task()).startswith("import random\n")
    rec = _validate(_task())
    assert rec["skeleton_baseline"] == "ok"
    assert rec["tests"]["test_constructor_only"]["trivial"]
    assert not rec["tests"]["test_behavioural"]["trivial"]


def test_scenario_nondeterminism_is_masked_not_excluded():
    sc = _validate(_task())["scenarios"]
    assert "test_nondeterministic" in sc["masks"]
    assert sc["n_usable"] == sc["n_original"]
    assert sc["env_observations_dropped"] == 2


def test_malformed_skeleton_is_excluded():
    rec = _validate(_task(prompt="class Bag:\n    def f(self:\n"))
    assert (rec["status"], rec["exclusion_reason"]) == ("excluded", "malformed_skeleton")


def test_vacuous_suite_is_excluded():
    rec = _validate(_task(test_code="def test_case_0():\n    dict_0 = {}\n"))
    assert rec["exclusion_reason"] == "invalid_vacuous_suite"


def test_missing_dependency_is_excluded():
    rec = _validate(_task(reference_code="import a_package_that_does_not_exist\n" + REFERENCE))
    assert rec["exclusion_reason"] == "missing_dependency"
    assert rec["detail"] == "EXC:builtins.ModuleNotFoundError"


def test_no_valid_tests_is_excluded():
    tests = TESTS.split("def test_behavioural")[0] + (
        "def test_case_0():\n    bag_0 = module_0.Bag(1)\n    assert bag_0.n == 2\n")
    rec = _validate(_task(test_code=tests))
    assert rec["exclusion_reason"] == "no_valid_tests"
