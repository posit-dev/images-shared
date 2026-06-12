import pytest

from posit_bakery.parallel import CommandResult, RetryPolicy
from posit_bakery.plugins.builtin.imagetools.retry import (
    DEFAULT_REGISTRY_RETRY,
    is_transient_registry_error,
)

pytestmark = [pytest.mark.unit]


def _result(stderr=b"", returncode=1, timed_out=False, exception=None):
    return CommandResult(
        cmd=["oras"],
        returncode=returncode,
        stdout=b"",
        stderr=stderr,
        duration=0.0,
        timed_out=timed_out,
        exception=exception,
    )


class TestIsTransientRegistryError:
    @pytest.mark.parametrize(
        "stderr",
        [
            b"Error: ghcr.io/x/tmp@sha256:abc: not found",
            b"failed to resolve: manifest unknown",
            b"unexpected status: 503 Service Unavailable",
            b"502 Bad Gateway",
            b"500 Internal Server Error",
            b"dial tcp: connection refused",
            b"net/http: TLS handshake timeout",
            b"unexpected EOF",
            b"Too Many Requests",
        ],
    )
    def test_transient_errors_match(self, stderr):
        assert is_transient_registry_error(_result(stderr=stderr)) is True

    @pytest.mark.parametrize(
        "stderr",
        [
            b"401 Unauthorized",
            b"unexpected status: 403 Forbidden",
            b"denied: requested access to the resource is denied",
            b"invalid reference format",
            b"some entirely unrelated error",
        ],
    )
    def test_permanent_or_unknown_errors_do_not_match(self, stderr):
        assert is_transient_registry_error(_result(stderr=stderr)) is False

    def test_timeout_is_transient(self):
        assert is_transient_registry_error(_result(timed_out=True)) is True

    def test_success_is_not_retryable(self):
        assert is_transient_registry_error(_result(returncode=0)) is False

    def test_case_insensitive(self):
        assert is_transient_registry_error(_result(stderr=b"MANIFEST NOT FOUND")) is True


def test_default_registry_retry_uses_classifier():
    assert isinstance(DEFAULT_REGISTRY_RETRY, RetryPolicy)
    assert DEFAULT_REGISTRY_RETRY.retry_on is is_transient_registry_error
    assert DEFAULT_REGISTRY_RETRY.max_attempts >= 2
