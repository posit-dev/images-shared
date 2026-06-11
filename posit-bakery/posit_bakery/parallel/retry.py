from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from posit_bakery.parallel.executor import CommandResult


@dataclass
class RetryPolicy:
    """Retry-with-backoff configuration for a single tracked command.

    Backoff is exponential and capped: the delay before the retry that follows a given
    (1-based) attempt is ``base_delay * multiplier**(attempt-1)``, clamped to ``max_delay``.
    With ``jitter`` enabled the delay is randomized within ``[0, capped]`` (full jitter) to
    avoid synchronized retry storms across parallel jobs.

    ``retry_on`` decides whether a *failed* result is worth retrying (e.g. a transient
    registry error vs. a permanent auth failure). When it is ``None`` nothing is retried.
    """

    max_attempts: int = 5
    base_delay: float = 2.0
    max_delay: float = 32.0
    multiplier: float = 2.0
    jitter: bool = True
    retry_on: Callable[[CommandResult], bool] | None = None

    def delay_for(self, attempt: int) -> float:
        """Backoff delay (seconds) before the retry that follows ``attempt`` (1-based)."""
        capped = min(self.base_delay * self.multiplier ** max(0, attempt - 1), self.max_delay)
        if self.jitter:
            return random.uniform(0.0, capped)
        return capped

    def should_retry(self, result: CommandResult, attempt: int) -> bool:
        """True when ``result`` (which just failed on ``attempt``) should be retried.

        :param result: The outcome of the just-finished attempt.
        :param attempt: The 1-based attempt number that produced ``result``.
        """
        if attempt >= self.max_attempts:
            return False
        if self.retry_on is None:
            return False
        if getattr(result, "ok", False):
            return False
        return self.retry_on(result)
