"""OpenAI-compatible chat completions provider."""

from __future__ import annotations

import asyncio
import json
import os
import random
from typing import Any

import httpx

from metis.config import DEFAULT_MODEL, DEFAULT_TEMPERATURE, MAX_TIMEOUT
from metis.logging import get_logger
from metis.providers.base import BaseProvider, ProviderCapabilities
from metis.providers.parsers.openai_native import OpenAINativeParser
from metis.providers.parsers.repair import ParserChain
from metis.providers.response_cache import ResponseCache
from metis.runtime.errors import ProviderError
from collections.abc import AsyncIterator

from metis.runtime.response import NormalizedResponse, StreamChunk

logger = get_logger("provider")


class OpenAICompatibleProvider(BaseProvider):
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 60.0,
        max_retries: int | None = None,
        retry_backoff_seconds: float | None = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("METIS_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("METIS_API_KEY", "")
        self.model = model or os.getenv("METIS_MODEL", DEFAULT_MODEL)
        self.timeout = min(timeout, MAX_TIMEOUT)
        self.max_retries = max_retries if max_retries is not None else _env_int("METIS_PROVIDER_MAX_RETRIES", 3)
        self.retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else _env_float("METIS_PROVIDER_RETRY_BACKOFF_SECONDS", 2.0)
        )
        if not self.base_url:
            raise ProviderError("Provider base_url is required. Set METIS_BASE_URL or pass base_url=")
        if not self.api_key:
            raise ProviderError("Provider api_key is required. Set METIS_API_KEY or pass api_key=")
        self.native_parser = OpenAINativeParser()
        self.text_parser = ParserChain()
        self._client: httpx.AsyncClient | None = None
        self._response_cache: ResponseCache | None = None
        if _env_bool("METIS_PROVIDER_RESPONSE_CACHE", False):
            max_size = _env_int("METIS_PROVIDER_CACHE_MAX_SIZE", 256)
            ttl = _env_float("METIS_PROVIDER_CACHE_TTL_SECONDS", 300.0)
            self._response_cache = ResponseCache(max_size=max_size, ttl_seconds=ttl)

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
            )
        return self._client

    async def close(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> dict[str, Any]:
        try:
            client = self._get_client()
            headers: dict[str, str] = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"
            resp = await client.get(f"{self.base_url}/models", headers=headers, timeout=10.0)
            if resp.status_code == 200:
                return {"status": "ok", "model": self.model, "endpoint": f"{self.base_url}/models"}
            return {"status": "error", "error": f"HTTP {resp.status_code}", "model": self.model}
        except Exception as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}", "model": self.model}

    async def __aenter__(self) -> OpenAICompatibleProvider:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    _MODEL_CAPABILITIES: dict[str, dict[str, Any]] = {
        "glm-4.9": {"thinking": True, "streaming": True, "max_context_tokens": 256_000, "max_output_tokens": 16_384},
        "glm-4.7": {"thinking": True, "streaming": True, "max_context_tokens": 128_000, "max_output_tokens": 8_192},
        "glm-4.5": {"thinking": True, "streaming": True, "max_context_tokens": 128_000, "max_output_tokens": 8_192},
        "glm-4": {"thinking": False, "streaming": True, "max_context_tokens": 128_000, "max_output_tokens": 4_096},
        "gpt-4o-mini": {"thinking": False, "streaming": True, "max_context_tokens": 128_000, "max_output_tokens": 16_384},
        "gpt-4o": {"thinking": False, "streaming": True, "max_context_tokens": 128_000, "max_output_tokens": 16_384},
        "gpt-4": {"thinking": False, "streaming": True, "max_context_tokens": 128_000, "max_output_tokens": 8_192},
        "claude-3-5-sonnet": {"thinking": False, "streaming": True, "max_context_tokens": 200_000, "max_output_tokens": 8_192},
        "claude-3-5-haiku": {"thinking": False, "streaming": True, "max_context_tokens": 200_000, "max_output_tokens": 4_096},
    }

    @classmethod
    def register_model_capabilities(cls, prefix: str, caps: dict[str, Any]) -> None:
        cls._MODEL_CAPABILITIES[prefix] = caps

    def capabilities(self) -> ProviderCapabilities:
        model_lower = self.model.lower()
        detected = self._detect_model_capabilities(model_lower)
        return ProviderCapabilities(
            provider_type="openai_compatible",
            model=self.model,
            native_tool_calling=True,
            json_schema_output=_env_bool("METIS_PROVIDER_JSON_SCHEMA_SUPPORTED", detected.get("json_schema_output", False)),
            streaming=_env_bool("METIS_PROVIDER_STREAMING_SUPPORTED", detected.get("streaming", False)),
            thinking=_env_bool("METIS_PROVIDER_THINKING_SUPPORTED", detected.get("thinking", False)),
            max_context_tokens=_env_int("METIS_PROVIDER_MAX_CONTEXT_TOKENS", detected.get("max_context_tokens", 0)),
            max_output_tokens=_env_int("METIS_PROVIDER_MAX_OUTPUT_TOKENS", detected.get("max_output_tokens", 0)),
        )

    @classmethod
    def _detect_model_capabilities(cls, model_lower: str) -> dict[str, Any]:
        """Infer capabilities from known model name patterns."""
        for prefix, caps in cls._MODEL_CAPABILITIES.items():
            if prefix in model_lower:
                return dict(caps)
        return {}

    async def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **params: Any,
    ) -> NormalizedResponse:
        if not self.base_url or not self.api_key:
            raise ProviderError("METIS_BASE_URL and METIS_API_KEY are required")

        payload: dict[str, Any] = {
            "model": params.pop("model", self.model),
            "messages": messages,
            "temperature": params.pop("temperature", DEFAULT_TEMPERATURE),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = params.pop("tool_choice", "auto")
        payload.update(params)

        env_max = os.getenv("METIS_PROVIDER_MAX_TOKENS")
        if env_max:
            payload["max_tokens"] = int(env_max)
        elif "max_tokens" not in payload:
            caps = self.capabilities()
            if caps.max_output_tokens > 0:
                payload["max_tokens"] = caps.max_output_tokens

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        if self._response_cache is not None:
            cached = self._response_cache.get(messages, tools)
            if cached is not None:
                logger.debug("Cache hit for messages hash")
                return self._parse_response(cached)

        client = self._get_client()
        data = await self._post_with_retries(client, url, headers, payload)
        if self._response_cache is not None:
            self._response_cache.put(messages, tools, data)
        return self._parse_response(data)

    async def complete_stream(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        **params: Any,
    ) -> AsyncIterator[StreamChunk]:
        if not self.base_url or not self.api_key:
            raise ProviderError("METIS_BASE_URL and METIS_API_KEY are required")

        payload: dict[str, Any] = {
            "model": params.pop("model", self.model),
            "messages": messages,
            "temperature": params.pop("temperature", DEFAULT_TEMPERATURE),
            "stream": True,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = params.pop("tool_choice", "auto")
        payload.update(params)

        env_max = os.getenv("METIS_PROVIDER_MAX_TOKENS")
        if env_max:
            payload["max_tokens"] = int(env_max)
        elif "max_tokens" not in payload:
            caps = self.capabilities()
            if caps.max_output_tokens > 0:
                payload["max_tokens"] = caps.max_output_tokens

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        client = self._get_client()
        accumulated_content = ""
        accumulated_reasoning: str | None = None
        accumulated_tool_calls: list[dict[str, Any]] = []
        finish_reason = ""
        usage: dict[str, Any] = {}

        try:
            async with client.stream("POST", url, headers=headers, json=payload, timeout=self.timeout) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    line = line.strip()
                    if not line or line.startswith(":"):
                        continue
                    if not line.startswith("data: "):
                        continue
                    data_str = line[len("data: "):].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(data_str)
                    except Exception:
                        continue
                    choices = chunk_data.get("choices", [{}])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    delta_content = delta.get("content") or ""
                    delta_reasoning = delta.get("reasoning_content") or delta.get("reasoning")
                    delta_tool_calls = delta.get("tool_calls") or []
                    chunk_finish = choices[0].get("finish_reason") or ""

                    if delta_content:
                        accumulated_content += delta_content
                    if delta_reasoning:
                        if accumulated_reasoning is None:
                            accumulated_reasoning = ""
                        accumulated_reasoning += delta_reasoning
                    if delta_tool_calls:
                        for tc in delta_tool_calls:
                            index = tc.get("index", 0)
                            while len(accumulated_tool_calls) <= index:
                                accumulated_tool_calls.append({"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                            existing = accumulated_tool_calls[index]
                            if tc.get("id"):
                                existing["id"] = tc["id"]
                            if tc.get("type"):
                                existing["type"] = tc["type"]
                            func = tc.get("function", {})
                            if func.get("name"):
                                existing["function"]["name"] += func["name"]
                            if func.get("arguments"):
                                existing["function"]["arguments"] += func["arguments"]

                    if chunk_finish:
                        finish_reason = chunk_finish

                    chunk_usage = chunk_data.get("usage")
                    if chunk_usage:
                        usage = chunk_usage

                    yield StreamChunk(
                        content=delta_content,
                        reasoning=delta_reasoning,
                        tool_calls=None,
                        is_finished=False,
                        usage=usage if chunk_usage else {},
                    )
        except Exception as exc:
            raise ProviderError(f"Streaming request failed: {exc}") from exc

        # Final chunk with accumulated data
        parsed_tool_calls = self.native_parser.parse(accumulated_tool_calls) if accumulated_tool_calls else []
        yield StreamChunk(
            content=accumulated_content,
            reasoning=accumulated_reasoning,
            tool_calls=parsed_tool_calls if parsed_tool_calls else None,
            is_finished=True,
            usage=usage,
        )

    def _parse_response(self, data: dict[str, Any]) -> NormalizedResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content") or ""
        native_calls = message.get("tool_calls") or []
        tool_calls = self.native_parser.parse(native_calls) if native_calls else []
        reasoning = message.get("reasoning_content") or message.get("reasoning")

        return NormalizedResponse(
            content=content,
            reasoning=reasoning,
            tool_calls=tool_calls,
            finish_reason=choice.get("finish_reason", ""),
            usage=data.get("usage", {}),
            raw=data,
        )

    async def _post_with_retries(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        last_error: Exception | None = None
        attempts = max(1, self.max_retries + 1)
        for attempt in range(1, attempts + 1):
            response: httpx.Response | None = None
            try:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                last_error = exc
                logger.warning("Provider attempt %d/%d failed: %s", attempt, attempts, exc)
                if attempt >= attempts or not _is_retryable_provider_error(exc, response):
                    break
                await asyncio.sleep(_retry_delay_seconds(response, attempt, self.retry_backoff_seconds))
        raise ProviderError(f"Provider request failed after {attempts} attempt(s): {last_error}") from last_error


def _is_retryable_provider_error(exc: Exception, response: httpx.Response | None) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if response is None:
        return False
    return response.status_code == 429 or 500 <= response.status_code < 600


def _retry_delay_seconds(response: httpx.Response | None, attempt: int, base_delay: float) -> float:
    if response is not None:
        retry_after = response.headers.get("retry-after")
        if retry_after:
            try:
                return max(0.0, min(float(retry_after), 30.0))
            except ValueError:
                pass
    exponential = min(max(0.0, base_delay) * (2 ** (attempt - 1)), 30.0)
    jitter = exponential * random.uniform(0.0, 0.25)
    return min(exponential + jitter, 30.0)


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, str(default))))
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
