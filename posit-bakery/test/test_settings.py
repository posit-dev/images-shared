import pytest

from posit_bakery.const import DEFAULT_MAX_CONCURRENCY
from posit_bakery.settings import Settings

pytestmark = [pytest.mark.unit]


class TestSettingsMaxConcurrency:
    def test_defaults_to_constant(self, monkeypatch):
        monkeypatch.delenv("BAKERY_MAX_CONCURRENCY", raising=False)
        assert Settings().max_concurrency == DEFAULT_MAX_CONCURRENCY

    def test_reads_env_var(self, monkeypatch):
        monkeypatch.setenv("BAKERY_MAX_CONCURRENCY", "9")
        assert Settings().max_concurrency == 9
