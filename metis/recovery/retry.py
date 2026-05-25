"""Retry policy with capped jittered backoff."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from metis.recovery.classifier import ErrorCategory


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    base_delay: float = 0.25
    max_delay: float = 5.0
    retryable_categories: set[str] = field(
        default_factory=lambda: {ErrorCategory.NETWORK, ErrorCategory.RATE_LIMIT, ErrorCategory.PROVIDER}
    )

    def should_retry(self, category: str, attempt: int) -> bool:
        return category in self.retryable_categories and attempt < self.max_retries

    def delay_for(self, attempt: int, *, rng: random.Random | None = None) -> float:
        rng = rng or random.Random()
        exponential = min(self.max_delay, self.base_delay * (2 ** max(0, attempt)))
        jitter = rng.uniform(0, exponential * 0.25)
        return min(self.max_delay, exponential + jitter)
