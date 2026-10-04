"""Benchmark adapters (Tier 1 / Tier 2).

RQ code obtains its benchmark through :func:`get_benchmark` and talks to it
only through the :mod:`.base` contract; see that module for the
architectural principle this package exists to enforce.

Modules:

- ``base.py``          the contract: ``Task``, ``SuiteResult``, ``DegradedSuite``,
                       ``InputPool`` and the capability protocols.
- ``humaneval.py``     Tier 1 adapter: verbatim delegation to existing code.
- ``realclasseval.py`` Tier 2 adapter.
- ``outcomes.py``      D1: the per-test outcome vocabulary.
- ``gate.py``          D2: test validity vs. reference correctness.
- ``scoring.py``       D3: pass-rate policies.
- ``scenarios.py``     D4: scenario extraction and the input pool.
- ``observe.py``       D5: the canonical observation serializer.
- ``forkserver.py``    D6: isolated scenario execution.

Adapters are imported lazily, so importing this package (as every RQ module
will) never pulls in either benchmark's dependencies or creates an import
cycle with the legacy modules the HumanEval adapter delegates to.
"""

from __future__ import annotations

from .base import Benchmark


def get_benchmark(cfg) -> Benchmark:
    """The adapter named by ``cfg.benchmark.name``."""
    name = cfg.benchmark.name.lower()
    if name == "humaneval":
        from .humaneval import HumanEvalBenchmark
        return HumanEvalBenchmark(cfg)
    if name == "realclasseval":
        from .realclasseval import RealClassEvalBenchmark
        return RealClassEvalBenchmark(cfg)
    raise ValueError(f"unknown benchmark.name {cfg.benchmark.name!r} "
                     "(expected 'humaneval' or 'realclasseval')")
