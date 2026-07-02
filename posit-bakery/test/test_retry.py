"""Tests for the retry-with-backoff helper."""

from unittest.mock import patch

import pytest

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.retry import RetryPolicy, is_transient_error, retry_on_transient

pytestmark = [pytest.mark.unit]


def _tool_error(message="oras command failed", stderr=b"", exit_code=1):
    return BakeryToolRuntimeError(
        message=message,
        tool_name="oras",
        cmd=["oras", "manifest", "fetch"],
        stdout=b"",
        stderr=stderr,
        exit_code=exit_code,
    )


class TestIsTransientError:
    @pytest.mark.parametrize(
        "stderr",
        [
            b"ghcr.io/posit-dev/workbench/tmp@sha256:abc: not found",
            b"manifest unknown",
            b"blob unknown to registry",
            b"received unexpected HTTP status: 503 Service Unavailable",
            b"429 Too Many Requests",
            b"net/http: request canceled (Client.Timeout exceeded)",
            b"dial tcp: i/o timeout",
            b"read tcp: connection reset by peer",
            b"unexpected EOF",
        ],
    )
    def test_detects_transient(self, stderr):
        assert is_transient_error(_tool_error(stderr=stderr)) is True

    @pytest.mark.parametrize(
        "stderr",
        [
            b"unauthorized: authentication required",
            b"denied: requested access to the resource is denied",
            b"invalid reference format",
            b"",
        ],
    )
    def test_non_transient(self, stderr):
        assert is_transient_error(_tool_error(stderr=stderr)) is False

    def test_matches_against_message_too(self):
        err = _tool_error(message="could not find the manifest: not found", stderr=b"")
        assert is_transient_error(err) is True


class TestRetryOnTransient:
    def test_returns_on_first_success(self):
        calls = []

        def fn():
            calls.append(1)
            return "ok"

        with patch("posit_bakery.retry.time.sleep") as sleep:
            result = retry_on_transient(fn, policy=RetryPolicy(max_attempts=5))

        assert result == "ok"
        assert len(calls) == 1
        sleep.assert_not_called()

    def test_retries_then_succeeds(self):
        attempts = {"n": 0}

        def fn():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise _tool_error(stderr=b"sha256:deadbeef: not found")
            return "ok"

        with patch("posit_bakery.retry.time.sleep") as sleep:
            result = retry_on_transient(
                fn, policy=RetryPolicy(max_attempts=5, initial_backoff=2.0, multiplier=2.0, max_backoff=32.0)
            )

        assert result == "ok"
        assert attempts["n"] == 3
        # Slept before attempt 2 and attempt 3: 2s then 4s (exponential).
        assert [c.args[0] for c in sleep.call_args_list] == [2.0, 4.0]

    def test_non_transient_fails_fast(self):
        attempts = {"n": 0}

        def fn():
            attempts["n"] += 1
            raise _tool_error(stderr=b"unauthorized: authentication required")

        with patch("posit_bakery.retry.time.sleep") as sleep:
            with pytest.raises(BakeryToolRuntimeError):
                retry_on_transient(fn, policy=RetryPolicy(max_attempts=5))

        assert attempts["n"] == 1
        sleep.assert_not_called()

    def test_exhausts_and_reraises_last_error(self):
        attempts = {"n": 0}

        def fn():
            attempts["n"] += 1
            raise _tool_error(stderr=b"sha256:abc: not found")

        with patch("posit_bakery.retry.time.sleep") as sleep:
            with pytest.raises(BakeryToolRuntimeError):
                retry_on_transient(fn, policy=RetryPolicy(max_attempts=3, initial_backoff=1.0))

        assert attempts["n"] == 3
        # Slept between the 3 attempts (after attempt 1 and 2).
        assert sleep.call_count == 2

    def test_backoff_is_capped_at_max(self):
        def fn():
            raise _tool_error(stderr=b"503 service unavailable")

        with patch("posit_bakery.retry.time.sleep") as sleep:
            with pytest.raises(BakeryToolRuntimeError):
                retry_on_transient(
                    fn,
                    policy=RetryPolicy(max_attempts=5, initial_backoff=10.0, multiplier=10.0, max_backoff=20.0),
                )

        # 10, then 100->capped 20, then 20, then 20.
        assert [c.args[0] for c in sleep.call_args_list] == [10.0, 20.0, 20.0, 20.0]

    def test_uses_provided_sleep_callable_instead_of_time_sleep(self):
        attempts = {"n": 0}
        sleep_calls = []

        def fn():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise _tool_error(stderr=b"sha256:deadbeef: not found")
            return "ok"

        def fake_sleep(seconds):
            sleep_calls.append(seconds)

        with patch("posit_bakery.retry.time.sleep") as real_sleep:
            result = retry_on_transient(fn, policy=RetryPolicy(max_attempts=5, initial_backoff=2.0), sleep=fake_sleep)

        assert result == "ok"
        assert sleep_calls == [2.0]
        real_sleep.assert_not_called()

    def test_none_sleep_falls_back_to_time_sleep(self):
        attempts = {"n": 0}

        def fn():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise _tool_error(stderr=b"sha256:deadbeef: not found")
            return "ok"

        with patch("posit_bakery.retry.time.sleep") as real_sleep:
            result = retry_on_transient(fn, policy=RetryPolicy(max_attempts=5, initial_backoff=2.0), sleep=None)

        assert result == "ok"
        real_sleep.assert_called_once_with(2.0)


class TestRetryPolicyEnv:
    def test_reads_defaults_from_env(self, monkeypatch):
        monkeypatch.setenv("BAKERY_REGISTRY_RETRY_ATTEMPTS", "9")
        monkeypatch.setenv("BAKERY_REGISTRY_RETRY_INITIAL_BACKOFF", "1.5")
        monkeypatch.setenv("BAKERY_REGISTRY_RETRY_MAX_BACKOFF", "60")
        monkeypatch.setenv("BAKERY_REGISTRY_RETRY_MULTIPLIER", "3")
        policy = RetryPolicy()
        assert policy.max_attempts == 9
        assert policy.initial_backoff == 1.5
        assert policy.max_backoff == 60.0
        assert policy.multiplier == 3.0

    def test_invalid_env_falls_back_to_default(self, monkeypatch):
        monkeypatch.setenv("BAKERY_REGISTRY_RETRY_ATTEMPTS", "not-a-number")
        policy = RetryPolicy()
        assert policy.max_attempts == 5
