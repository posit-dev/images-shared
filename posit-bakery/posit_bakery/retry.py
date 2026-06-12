"""Retry-with-backoff helpers for transient registry errors.

Registry-touching operations (oras manifest index create, oras cp, oras
manifest fetch, the SOCI pull/push) intermittently fail against registries
that exhibit read-after-write (eventual consistency) behaviour — most visibly
GHCR, where a manifest pushed *by digest* from one runner is briefly
unreadable by digest from another. The failure is transient: the manifest is
durably present, just not yet replicated when first requested.

:func:`retry_on_transient` wraps a registry call so that *transient* failures
(``not found`` / ``manifest unknown`` / 5xx / timeouts / rate limits) are
retried a handful of times with exponential backoff, while non-transient
failures still fail fast. Counts and timings are configurable via the
``BAKERY_REGISTRY_RETRY_*`` environment variables.
"""

import logging
import os
import re
import time
from typing import Annotated, Callable, TypeVar

from pydantic import BaseModel, Field

from posit_bakery.error import BakeryToolRuntimeError

log = logging.getLogger(__name__)

T = TypeVar("T")

# Substrings/patterns (matched case-insensitively against the failed command's
# message + stdout + stderr) that mark an error as transient and worth
# retrying. Anything not matched here fails fast — a genuine bad reference,
# auth failure, or malformed manifest should not be retried.
_TRANSIENT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"not found",
        r"manifest unknown",
        r"blob unknown",
        r"name unknown",
        r"\b5\d\d\b",  # 5xx HTTP status codes
        r"\b429\b",  # too many requests
        r"too many requests",
        r"temporarily unavailable",
        r"timeout",
        r"timed out",
        r"i/o timeout",
        r"connection reset",
        r"connection refused",
        r"\beof\b",
    )
)


def _env_int(name: str, default: int, min_value: int = 0) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        log.warning(f"Ignoring invalid {name}={raw!r}; using default {default}.")
        return default
    if value < min_value:
        log.warning(f"Ignoring {name}={raw!r}; using default {default}.")
        return default
    return value


def _env_float(name: str, default: float, min_value: float = 0.0) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        log.warning(f"Ignoring invalid {name}={raw!r}; using default {default}.")
        return default
    if value < min_value:
        log.warning(f"Ignoring {name}={raw!r}; using default {default}.")
        return default
    return value


class RetryPolicy(BaseModel):
    """Exponential-backoff retry configuration.

    Defaults are read from the environment at construction time so CI can tune
    them without code changes:

    - ``BAKERY_REGISTRY_RETRY_ATTEMPTS`` (default 5)
    - ``BAKERY_REGISTRY_RETRY_INITIAL_BACKOFF`` seconds (default 2.0)
    - ``BAKERY_REGISTRY_RETRY_MAX_BACKOFF`` seconds (default 32.0)
    - ``BAKERY_REGISTRY_RETRY_MULTIPLIER`` (default 2.0)
    """

    max_attempts: Annotated[int, Field(default_factory=lambda: _env_int("BAKERY_REGISTRY_RETRY_ATTEMPTS", 5, 1), ge=1)]
    initial_backoff: Annotated[
        float, Field(default_factory=lambda: _env_float("BAKERY_REGISTRY_RETRY_INITIAL_BACKOFF", 2.0, 0), ge=0)
    ]
    max_backoff: Annotated[
        float, Field(default_factory=lambda: _env_float("BAKERY_REGISTRY_RETRY_MAX_BACKOFF", 32.0, 0), ge=0)
    ]
    multiplier: Annotated[
        float, Field(default_factory=lambda: _env_float("BAKERY_REGISTRY_RETRY_MULTIPLIER", 2.0, 1), ge=1)
    ]


def is_transient_error(error: BakeryToolRuntimeError) -> bool:
    """Return True if ``error`` looks like a transient registry error.

    The decision is text-based: the error's message plus a generous slice of
    its stdout/stderr are scanned for any known transient signature.
    """
    parts = [
        error.message or "",
        error.dump_stdout(lines=50),
        error.dump_stderr(lines=50),
    ]
    haystack = "\n".join(p for p in parts if p)
    return any(pattern.search(haystack) for pattern in _TRANSIENT_PATTERNS)


def retry_on_transient(
    func: Callable[[], T],
    *,
    policy: RetryPolicy | None = None,
    description: str = "registry operation",
) -> T:
    """Call ``func`` retrying transient :class:`BakeryToolRuntimeError`s.

    On a transient failure the call is retried up to ``policy.max_attempts``
    times with exponential backoff (``initial_backoff`` growing by
    ``multiplier``, capped at ``max_backoff``). Non-transient errors and the
    final transient error are re-raised unchanged.

    :param func: Zero-argument callable performing the registry operation.
    :param policy: Retry configuration; a default (env-tunable) policy is used
        when omitted.
    :param description: Human-readable label for log messages.
    :return: Whatever ``func`` returns on success.
    :raises BakeryToolRuntimeError: The last error if all attempts fail or the
        first non-transient error encountered.
    """
    policy = policy or RetryPolicy()
    backoff = policy.initial_backoff
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return func()
        except BakeryToolRuntimeError as e:
            if not is_transient_error(e):
                raise
            if attempt >= policy.max_attempts:
                log.error(
                    f"{description} failed after {attempt} attempt(s); giving up. Last error: {e.dump_stderr() or e}"
                )
                raise
            log.warning(
                f"{description} hit a transient registry error "
                f"(attempt {attempt}/{policy.max_attempts}); retrying in {backoff:.1f}s. "
                f"Error: {e.dump_stderr() or e}"
            )
            time.sleep(backoff)
            backoff = min(backoff * policy.multiplier, policy.max_backoff)
    # Unreachable: the loop either returns or raises on the final attempt.
    raise AssertionError("retry_on_transient exhausted its loop without returning or raising")
