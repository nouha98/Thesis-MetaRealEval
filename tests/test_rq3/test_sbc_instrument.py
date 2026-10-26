"""The SBC reverse generator is an instrument: never the model's inference condition.

A gemma "thinking on" profile applied to SBC would spend the fixed 256-token
budget on reasoning; any profile would make SBC scores depend on the condition
under test. The request body, temperature, budget and cache key must be exactly
the legacy ones, whatever profile the model carries.
"""

from __future__ import annotations

from types import SimpleNamespace

from meta_real_eval.core.cache import ResponseCache
from meta_real_eval.core.config import LLMConfig, LLMModelConfig, SamplingConfig
from meta_real_eval.core.llm_client import InnkubeClient
from meta_real_eval.rq3.sbc_scorer import _REVERSE_GEN_SYSTEM, compute_sbc_score


class _FakeOpenAI:
    def __init__(self):
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def with_options(self, **kw):
        return self

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content="adds two numbers", reasoning_content=None, reasoning=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason="stop")],
                               usage=None, model=kwargs["model"])


async def test_sbc_sends_the_legacy_request_whatever_the_profile(tmp_path):
    profiled = LLMModelConfig(
        id="gemma4-31b-it",
        request_params={"chat_template_kwargs": {"enable_thinking": True}},
        sampling=SamplingConfig(temperature=1.0, top_p=0.95, top_k=64))
    cache = ResponseCache(tmp_path / "cache")
    client = InnkubeClient(LLMConfig(models=[profiled]), cache, mock=False)
    fake = _FakeOpenAI()
    client._client = fake
    task = SimpleNamespace(prompt='def f(a, b):\n    """Add two numbers."""\n')
    code = "def f(a, b):\n    return a + b\n"

    await compute_sbc_score(task, code, "gemma4-31b-it", client)

    messages = [{"role": "system", "content": _REVERSE_GEN_SYSTEM},
                {"role": "user", "content": f"Function implementation:\n\n{code}"}]
    assert fake.calls == [{"model": "gemma4-31b-it", "messages": messages,
                           "temperature": 0.3, "max_tokens": 256, "n": 1}]
    assert cache.get(cache.key("gemma4-31b-it", messages, temperature=0.3,
                               max_tokens=256, n=1)) is not None, "not the legacy cache key"


def test_the_sbc_model_is_pinned_by_config_not_by_model_order():
    from meta_real_eval.core.config import Config
    cfg = Config.model_validate({"llm": {"models": [{"id": "qwen36-35b"}, {"id": "gemma4-31b-it"}]},
                                 "rq3": {"sbc_model": "gemma4-31b-it"}})
    assert (cfg.rq3.sbc_model or cfg.model_ids()[0]) == "gemma4-31b-it"
