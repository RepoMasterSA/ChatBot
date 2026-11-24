"""LiteLLM gateway: key pool, automatic failover and response caching."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

import litellm

from .config import Settings

log = logging.getLogger("chatbot.llm")


class AllProvidersUnavailable(Exception):
    """Every key in the pool failed for this request."""


class SimulatedProviderError(Exception):
    """Raised instead of calling the provider when X-Simulate-Failure targets a key."""

    def __init__(self, status: int) -> None:
        super().__init__(f"simulated provider error {status}")
        self.status = status


@dataclass
class LLMResult:
    reply: str
    cache_hit: bool
    key_id: str | None
    fallback_attempts: int
    input_tokens: int
    output_tokens: int
    model: str


def build_cache(settings: Settings) -> Any:
    if settings.cache_type == "disk":
        return litellm.Cache(type="disk", disk_cache_dir=settings.cache_dir)
    return litellm.Cache(type="local")  # in-memory


class LLMGateway:
    def __init__(
        self,
        settings: Settings,
        completion_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.settings = settings
        self._completion = completion_fn or litellm.completion
        litellm.suppress_debug_info = True
        litellm.drop_params = True
        # LiteLLM's built-in cache. Key = model + the full message list.
        litellm.cache = build_cache(settings)
        self.cache_enabled = True

    def complete(
        self, messages: list[dict[str, str]], simulate: dict[str, int] | None = None
    ) -> LLMResult:
        simulate = simulate or {}
        # Simulated requests must prove real failover, so they skip the cache.
        use_cache = not simulate
        attempts = 0

        for key_id, api_key in zip(self.settings.key_ids, self.settings.api_keys):
            try:
                status = simulate.get(key_id, simulate.get("*"))
                if status:
                    raise SimulatedProviderError(status)

                response = self._completion(
                    model=self.settings.model,
                    messages=messages,
                    api_key=api_key,
                    caching=use_cache,
                    num_retries=0,  # fail over to the next key instead of retrying
                    timeout=self.settings.request_timeout_s,
                )
                return self._to_result(response, messages, key_id, attempts)
            except Exception as exc:  # 429, quota, 5xx, timeouts, bad keys, empty replies
                attempts += 1
                log.warning(
                    "%s failed (%s: %s); trying next key",
                    key_id,
                    type(exc).__name__,
                    str(exc)[:200],
                )

        raise AllProvidersUnavailable()

    def _to_result(
        self,
        response: Any,
        messages: list[dict[str, str]],
        key_id: str,
        attempts: int,
    ) -> LLMResult:
        reply = (response.choices[0].message.content or "").strip()
        if not reply:
            raise ValueError("provider returned an empty reply")

        hidden = getattr(response, "_hidden_params", None) or {}
        cache_hit = bool(hidden.get("cache_hit"))

        usage = getattr(response, "usage", None)
        input_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
        if not input_tokens:
            input_tokens = litellm.token_counter(model=self.settings.model, messages=messages)
        if not output_tokens:
            output_tokens = litellm.token_counter(model=self.settings.model, text=reply)

        return LLMResult(
            reply=reply,
            cache_hit=cache_hit,
            key_id=None if cache_hit else key_id,
            fallback_attempts=0 if cache_hit else attempts,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.settings.model,
        )
