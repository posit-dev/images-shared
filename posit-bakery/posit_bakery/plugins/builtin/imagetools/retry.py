"""Retry policy for the registry-touching commands the publish pipeline runs.

Issue #591: GHCR eventual-consistency makes digest-addressed manifests intermittently report
as "not found" / "manifest unknown" when a sibling runner references them seconds after they
were pushed. These are transient and self-heal on a re-run, so we retry them with backoff;
permanent errors (auth, bad references) fail fast.
"""

from posit_bakery.parallel import CommandResult, RetryPolicy

# Upper bound on a single registry command before it is treated as hung and killed. Generous
# because a SOCI conversion pulls and rewrites a full image; ordinary oras calls finish quickly.
DEFAULT_COMMAND_TIMEOUT = 900.0

# Substrings (lower-cased) that mark a failure as a transient registry/network blip worth a retry.
_TRANSIENT_MARKERS = (
    "not found",
    "manifest unknown",
    "blob unknown",
    "500 internal server error",
    "internal server error",
    "502 bad gateway",
    "bad gateway",
    "503 service unavailable",
    "service unavailable",
    "504 gateway timeout",
    "gateway timeout",
    "too many requests",
    "connection refused",
    "connection reset",
    "i/o timeout",
    "tls handshake timeout",
    "temporarily unavailable",
    "unexpected eof",
    "eof",
)

# Substrings that mark a failure as permanent — never retried even if a transient marker also
# appears (auth/reference errors will not heal on their own).
_PERMANENT_MARKERS = (
    "401",
    "unauthorized",
    "403",
    "forbidden",
    "denied",
    "invalid reference",
)


def is_transient_registry_error(result: CommandResult) -> bool:
    """True when a failed command looks like a transient registry/network error worth retrying."""
    if result.ok:
        return False
    if result.timed_out:
        return True
    stderr = (result.stderr or b"").decode("utf-8", errors="replace").lower()
    if any(marker in stderr for marker in _PERMANENT_MARKERS):
        return False
    return any(marker in stderr for marker in _TRANSIENT_MARKERS)


# Hardcoded sensible defaults: up to 5 attempts, exponential 2s -> 32s with full jitter.
DEFAULT_REGISTRY_RETRY = RetryPolicy(retry_on=is_transient_registry_error)
