from types import SimpleNamespace

import pytest

from posit_bakery.parallel import RetryPolicy

pytestmark = [pytest.mark.unit]


def _result(ok: bool):
    """A minimal CommandResult stand-in for policy tests (only `.ok` is read)."""
    return SimpleNamespace(ok=ok)


class TestRetryPolicyDelayFor:
    def test_exponential_growth_without_jitter(self):
        policy = RetryPolicy(base_delay=2.0, multiplier=2.0, max_delay=32.0, jitter=False)
        assert policy.delay_for(1) == 2.0
        assert policy.delay_for(2) == 4.0
        assert policy.delay_for(3) == 8.0
        assert policy.delay_for(4) == 16.0
        assert policy.delay_for(5) == 32.0

    def test_capped_at_max_delay(self):
        policy = RetryPolicy(base_delay=2.0, multiplier=2.0, max_delay=32.0, jitter=False)
        assert policy.delay_for(6) == 32.0
        assert policy.delay_for(10) == 32.0

    def test_jitter_stays_within_zero_and_cap(self):
        policy = RetryPolicy(base_delay=2.0, multiplier=2.0, max_delay=32.0, jitter=True)
        for attempt in range(1, 8):
            uncapped = min(2.0 * 2.0 ** (attempt - 1), 32.0)
            for _ in range(50):
                delay = policy.delay_for(attempt)
                assert 0.0 <= delay <= uncapped


class TestRetryPolicyShouldRetry:
    def _policy(self, **kw):
        kw.setdefault("retry_on", lambda r: True)
        return RetryPolicy(max_attempts=5, **kw)

    def test_retries_transient_failure_below_attempt_cap(self):
        policy = self._policy(retry_on=lambda r: True)
        assert policy.should_retry(_result(ok=False), attempt=1) is True

    def test_no_retry_at_attempt_cap(self):
        policy = self._policy(retry_on=lambda r: True)
        assert policy.should_retry(_result(ok=False), attempt=5) is False

    def test_no_retry_when_result_ok(self):
        policy = self._policy(retry_on=lambda r: True)
        assert policy.should_retry(_result(ok=True), attempt=1) is False

    def test_no_retry_when_predicate_rejects(self):
        policy = self._policy(retry_on=lambda r: False)
        assert policy.should_retry(_result(ok=False), attempt=1) is False

    def test_no_retry_when_no_predicate(self):
        policy = RetryPolicy(max_attempts=5, retry_on=None)
        assert policy.should_retry(_result(ok=False), attempt=1) is False


class TestRetryPolicyDefaults:
    def test_default_field_values(self):
        policy = RetryPolicy()
        assert policy.max_attempts == 5
        assert policy.base_delay == 2.0
        assert policy.max_delay == 32.0
        assert policy.multiplier == 2.0
        assert policy.jitter is True
        assert policy.retry_on is None
