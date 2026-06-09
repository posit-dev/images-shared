import pytest

from posit_bakery.const import DEFAULT_MAX_CONCURRENCY
from posit_bakery.parallel import ShellResult, ShellTask, resolve_max_workers

pytestmark = [pytest.mark.unit]


class TestShellTask:
    def test_display_label_defaults_to_key(self):
        task = ShellTask(key="abc", cmd=["true"])
        assert task.display_label == "abc"

    def test_display_label_uses_label_when_set(self):
        task = ShellTask(key="abc", cmd=["true"], label="My Label")
        assert task.display_label == "My Label"


class TestShellResult:
    def test_ok_true_on_zero_exit_no_exception(self):
        task = ShellTask(key="a", cmd=["true"])
        result = ShellResult(task=task, returncode=0, stdout=b"", stderr=b"", duration=0.0)
        assert result.ok is True

    def test_ok_false_on_nonzero_exit(self):
        task = ShellTask(key="a", cmd=["false"])
        result = ShellResult(task=task, returncode=1, stdout=b"", stderr=b"", duration=0.0)
        assert result.ok is False

    def test_ok_false_on_exception(self):
        task = ShellTask(key="a", cmd=["nope"])
        result = ShellResult(
            task=task, returncode=None, stdout=b"", stderr=b"", duration=0.0, exception=FileNotFoundError()
        )
        assert result.ok is False


class TestResolveMaxWorkers:
    def test_jobs_overrides_setting(self):
        assert resolve_max_workers(2, n_tasks=10) == 2

    def test_falls_back_to_setting(self, monkeypatch):
        monkeypatch.setattr("posit_bakery.parallel.executor.SETTINGS.max_concurrency", 3)
        assert resolve_max_workers(None, n_tasks=10) == 3

    def test_non_positive_jobs_ignored(self, monkeypatch):
        monkeypatch.setattr("posit_bakery.parallel.executor.SETTINGS.max_concurrency", 5)
        assert resolve_max_workers(0, n_tasks=10) == 5

    def test_clamped_to_n_tasks(self):
        assert resolve_max_workers(8, n_tasks=3) == 3

    def test_never_below_one(self, monkeypatch):
        monkeypatch.setattr("posit_bakery.parallel.executor.SETTINGS.max_concurrency", DEFAULT_MAX_CONCURRENCY)
        assert resolve_max_workers(None, n_tasks=0) == 1
