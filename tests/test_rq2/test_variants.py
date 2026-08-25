"""The three RQ2 arms, and the cache salt that makes the control arm real.

``control_resample`` submits the unmodified prompt as its own variant so that
sampling noise has a measured floor. Without a cache salt the second submission
hits the same ResponseCache key as ``original`` and returns byte-identical
completions, reporting a floor of exactly tau_b = 1.0 — the same artifact that
the no-op template relations already produce.
"""

import hashlib
import json

import pytest

from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.config import Config
from meta_real_eval.rq2.corpus import tasks_sha256
from meta_real_eval.rq2.generator import build_task_variants
from meta_real_eval.rq2.paraphraser import apply_relation
from meta_real_eval.rq2.ranking import collapse_tau_by_arm, relation_arm


# ---------------------------------------------------------------------------
# Cache salt
# ---------------------------------------------------------------------------

def test_salt_changes_the_cache_key(tmp_path):
    cache = ResponseCache(tmp_path)
    messages = [{"role": "user", "content": "hi"}]
    plain = cache.key("m", messages, temperature=0.8, max_tokens=10, n=1)
    salted = cache.key("m", messages, temperature=0.8, max_tokens=10, n=1,
                       cache_salt="control_resample")
    assert plain != salted


def test_no_salt_leaves_existing_keys_untouched(tmp_path):
    # Adding the parameter must not invalidate a single cached response: every
    # other call site passes nothing and has to keep hitting its existing entry,
    # so the unsalted key must still be the hash of exactly the old payload.
    cache = ResponseCache(tmp_path)
    messages = [{"role": "user", "content": "hi"}]
    blob = json.dumps({"model": "m", "messages": messages, "temperature": 0.8,
                       "max_tokens": 10, "n": 1}, sort_keys=True)
    assert cache.key("m", messages, temperature=0.8, max_tokens=10, n=1) == (
        hashlib.sha256(blob.encode()).hexdigest()
    )


@pytest.mark.asyncio
async def test_client_does_not_send_the_salt_to_the_api(tmp_path, monkeypatch):
    from meta_real_eval.core.config import LLMConfig
    from meta_real_eval.core.llm_client import InnkubeClient

    sent = {}

    class _Choice:
        def __init__(self, text):
            self.message = type("M", (), {"content": text})()

    async def fake_create(**kwargs):
        sent.update(kwargs)
        return type("R", (), {"choices": [_Choice("ok")]})()

    cache = ResponseCache(tmp_path)
    client = InnkubeClient(LLMConfig(), cache, mock=False)
    monkeypatch.setattr(
        client, "_get_client",
        lambda: type("C", (), {"chat": type("Ch", (), {
            "completions": type("Co", (), {"create": staticmethod(fake_create)})()
        })()})(),
    )

    out = await client.complete("m", [{"role": "user", "content": "hi"}],
                                cache_salt="control_resample")
    assert out == ["ok"]
    assert "cache_salt" not in sent


# ---------------------------------------------------------------------------
# Variant assembly
# ---------------------------------------------------------------------------

def test_control_resample_is_the_original_prompt_under_a_salt(simple_task, config):
    variants = build_task_variants(simple_task, config)
    original_text, original_salt = variants["original"]
    control_text, control_salt = variants["control_resample"]

    assert control_text == original_text == simple_task.prompt
    assert original_salt is None
    assert control_salt == "control_resample"


def test_template_arm_is_unchanged(simple_task, config):
    variants = build_task_variants(simple_task, config)
    for relation in config.rq2.template_relations:
        assert variants[relation][0] == apply_relation(simple_task.prompt, relation)
        assert variants[relation][1] is None


def test_corpus_variants_are_loaded_and_gaps_are_left_absent(simple_task, tmp_path):
    rewritten = 'def add(a: int, b: int) -> int:\n    """Compute the sum of a and b."""\n'
    corpus = {
        "manifest": {"families": ["lexical"], "n_per_family": 2},
        "tasks": {simple_task.task_id: {
            "original": simple_task.prompt,
            "variants": [{"variant_id": "llm_lexical_01", "family": "lexical",
                          "text": rewritten, "validation": {}}],
        }},
    }
    corpus["manifest"]["sha256"] = tasks_sha256(corpus)
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")

    cfg = Config.model_validate({"rq2": {"paraphrase_corpus": str(path)}})
    variants = build_task_variants(simple_task, cfg)

    assert variants["llm_lexical_01"] == (rewritten, None)
    # Slot 02 was declared but never filled. It stays absent — padding it with a
    # template would put back exactly the tautological cell the corpus removes.
    assert "llm_lexical_02" in cfg.rq2.relations
    assert "llm_lexical_02" not in variants


# ---------------------------------------------------------------------------
# No-op regression guard
# ---------------------------------------------------------------------------

def test_no_llm_variant_is_a_no_op_on_the_prompt(simple_task, tmp_path):
    """A corpus variant identical to the original would be a dead cell.

    Asserted on the *prompt*, not on the completions: a trivial task legitimately
    returns the same completion under every relation (HumanEval/2 returns
    `return number - int(number)` ten times out of ten for all three models), so
    comparing completions would flag correct behaviour as a defect. The prompt is
    what decides whether the cache key collides, so the prompt is what to check.
    """
    corpus = {
        "manifest": {"families": ["lexical"], "n_per_family": 1},
        "tasks": {simple_task.task_id: {
            "original": simple_task.prompt,
            "variants": [{"variant_id": "llm_lexical_01", "family": "lexical",
                          "text": simple_task.prompt, "validation": {}}],
        }},
    }
    corpus["manifest"]["sha256"] = tasks_sha256(corpus)
    path = tmp_path / "corpus.json"
    path.write_text(json.dumps(corpus), encoding="utf-8")

    cfg = Config.model_validate({"rq2": {"paraphrase_corpus": str(path)}})
    variants = build_task_variants(simple_task, cfg)

    no_ops = [
        relation for relation, (text, salt) in variants.items()
        if relation != "original" and salt is None and text == simple_task.prompt
    ]
    # This corpus was built to contain one, and the guard has to see it. Gate A
    # rejects such a variant at generation time (identical_to_original); this is
    # the downstream assertion that the guard itself works.
    assert "llm_lexical_01" in no_ops

    # The template arm is expected to contain no-ops — that is precisely what it
    # is retained to measure. On this prompt `reorder` finds no `>>>` block and
    # `terse` finds no filler, so both return the input unchanged, and their
    # cells would replay `original`'s completions.
    assert {"reorder", "terse"} <= set(no_ops)


# ---------------------------------------------------------------------------
# Arm collapse
# ---------------------------------------------------------------------------

def test_relation_arm_classification():
    assert relation_arm("original") == ("baseline", None)
    assert relation_arm("control_resample") == ("control", None)
    assert relation_arm("persona") == ("template", None)
    assert relation_arm("llm_lexical_03") == ("llm", "lexical")


def test_families_are_averaged_before_arms():
    # Three lexical variants must not outvote one terse variant: each family
    # contributes one value, then the families are averaged.
    tau = {
        "llm_lexical_01": 0.0, "llm_lexical_02": 0.0, "llm_lexical_03": 0.0,
        "llm_terse_01": 1.0,
    }
    collapsed = collapse_tau_by_arm(tau)
    assert collapsed["llm_by_family"] == {"lexical": 0.0, "terse": 1.0}
    assert collapsed["llm"] == pytest.approx(0.5)   # not 0.25


def test_arms_are_kept_separate():
    collapsed = collapse_tau_by_arm({
        "control_resample": 0.9, "persona": 0.8, "terse": 0.6,
        "llm_lexical_01": 0.2, "original": None,
    })
    assert collapsed["control"] == pytest.approx(0.9)
    assert collapsed["template"] == pytest.approx(0.7)
    assert collapsed["llm"] == pytest.approx(0.2)
    # The headline follows the LLM arm when a corpus is in play.
    assert collapsed["primary"] == pytest.approx(0.2)


def test_primary_falls_back_to_templates_without_a_corpus():
    collapsed = collapse_tau_by_arm({"control_resample": 0.9, "persona": 0.8,
                                     "terse": 0.6})
    assert collapsed["llm"] is None
    assert collapsed["primary"] == pytest.approx(0.7)


def test_undefined_taus_are_excluded_not_coerced():
    collapsed = collapse_tau_by_arm({"persona": None, "terse": 0.5})
    assert collapsed["template"] == pytest.approx(0.5)
