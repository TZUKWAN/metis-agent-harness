"""OpenAI-compatible chat completions provider."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx

from metis.providers.base import BaseProvider, ProviderCapabilities
from metis.providers.parsers.openai_native import OpenAINativeParser
from metis.providers.parsers.repair import ParserChain
from metis.runtime.errors import ProviderError
from metis.runtime.response import NormalizedResponse


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
        self.model = model or os.getenv("METIS_MODEL", "glm-4.7-flash")
        self.timeout = timeout
        self.max_retries = max_retries if max_retries is not None else _env_int("METIS_PROVIDER_MAX_RETRIES", 3)
        self.retry_backoff_seconds = (
            retry_backoff_seconds
            if retry_backoff_seconds is not None
            else _env_float("METIS_PROVIDER_RETRY_BACKOFF_SECONDS", 2.0)
        )
        self.native_parser = OpenAINativeParser()
        self.text_parser = ParserChain()

    def capabilities(self) -> ProviderCapabilities:
        model_lower = self.model.lower()
        return ProviderCapabilities(
            provider_type="openai_compatible",
            model=self.model,
            native_tool_calling=True,
            json_schema_output=_env_bool("METIS_PROVIDER_JSON_SCHEMA_SUPPORTED", False),
            streaming=False,
            thinking=_env_bool(
                "METIS_PROVIDER_THINKING_SUPPORTED",
                "glm-4.7" in model_lower or "glm-4.5" in model_lower,
            ),
            max_context_tokens=_env_int("METIS_PROVIDER_MAX_CONTEXT_TOKENS", 0),
            max_output_tokens=_env_int("METIS_PROVIDER_MAX_OUTPUT_TOKENS", 0),
        )

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
            "temperature": params.pop("temperature", 0.2),
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = params.pop("tool_choice", "auto")
        payload.update(params)

        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            data = await self._post_with_retries(client, url, headers, payload)

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
    return min(max(0.0, base_delay) * (2 ** (attempt - 1)), 30.0)


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
