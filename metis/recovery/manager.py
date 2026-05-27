"""Recovery manager for retryable operations."""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, TypeVar

from metis.events.hooks import HookBus
from metis.recovery.classifier import ErrorClassifier
from metis.recovery.retry import RetryPolicy

T = TypeVar("T")


class RecoveryManager:
    def __init__(
        self,
        *,
        classifier: ErrorClassifier | None = None,
        retry_policy: RetryPolicy | None = None,
        hooks: HookBus | None = None,
    ) -> None:
        self.classifier = classifier or ErrorClassifier()
        self.retry_policy = retry_policy or RetryPolicy()
        self.hooks = hooks or HookBus()

    def should_retry(self, error: BaseException | str, attempt: int) -> bool:
        return self.retry_policy.should_retry(self.classifier.classify(error), attempt)

    async def execute_with_recovery(self, operation: Callable[[], Awaitable[T]]) -> T:
        attempt = 0
        while True:
            try:
                return await operation()
            except Exception as exc:
                category = self.classifier.classify(exc)
                if not self.retry_policy.should_retry(category, attempt):
                    raise
                delay = self.retry_policy.delay_for(attempt)
                await self.hooks.emit_async("recovery.retry", {"attempt": attempt + 1, "category": category, "delay": delay})
                await asyncio.sleep(delay)
                attempt += 1

    def on_tool_error(self, error: BaseException | str, attempt: int) -> bool:
        return self.should_retry(error, attempt)

    def on_provider_error(self, error: BaseException | str, attempt: int) -> bool:
        return self.should_retry(error, attempt)
