"""scripts/probe_seeds.py runs end to end against a fake endpoint (no network)."""

import importlib.util
import json
import random
import sys
from pathlib import Path
from types import SimpleNamespace

import openai

REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("probe_seeds", REPO / "scripts" / "probe_seeds.py")
probe = importlib.util.module_from_spec(spec)
sys.modules["probe_seeds"] = probe
spec.loader.exec_module(probe)


class _FakeOpenAI:
    """Seeded child i of a request with seed s = rng(s + i); unseeded = fresh."""
    calls: list[dict] = []

    def __init__(self, **kw):
        create = SimpleNamespace(create=self._create)
        self.chat = SimpleNamespace(completions=SimpleNamespace(with_raw_response=create))

    def _create(self, **kw):
        _FakeOpenAI.calls.append(kw)
        seed = kw.get("seed")
        texts = [str(random.Random(seed + i).random()) if seed is not None else str(random.random())
                 for i in range(kw["n"])]
        choices = [SimpleNamespace(message=SimpleNamespace(content=t, reasoning_content=None))
                   for t in texts]
        resp = SimpleNamespace(choices=choices)
        return SimpleNamespace(parse=lambda: resp, headers={"x-litellm-cache-key": "k", "other": "x"})


def test_probe_reports_independent_seeded_draws(tmp_path, monkeypatch):
    monkeypatch.setattr(openai, "OpenAI", _FakeOpenAI)
    out = tmp_path / "probe.json"
    probe.main(["--config", str(REPO / "config" / "tier2_realclasseval.yaml"),
                "--model", "qwen38-27b", "--try-no-cache", "--out", str(out)])
    r = json.loads(out.read_text(encoding="utf-8"))
    assert r["T1_within_request"]["distinct"] == 10
    assert r["T2_child_seed_matches"] == 5, "fake follows vLLM's seed+index rule"
    assert r["T3_repeat_identical"] is True
    assert r["T4_across_seeds"]["texts_shared_across_requests"] == 0
    assert r["T5_unseeded_identical"] is False and r["T6_no_cache_identical"] is False
    assert r["T1_within_request"]["cache_headers"] == {"x-litellm-cache-key": "k"}
    sent = _FakeOpenAI.calls[0]
    assert sent["temperature"] == 1.0 and sent["extra_body"]["top_k"] == 20, "the model's card sampling"
    assert _FakeOpenAI.calls[-1]["extra_body"]["cache"] == {"no-cache": True}
