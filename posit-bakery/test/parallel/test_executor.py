import io
import os
import sys
import threading

import pytest
from rich.console import Console

from posit_bakery.const import DEFAULT_MAX_CONCURRENCY
from posit_bakery.parallel import ParallelShellExecutor, ShellResult, ShellTask, resolve_max_workers

PY = sys.executable

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

    def test_negative_jobs_ignored(self, monkeypatch):
        monkeypatch.setattr("posit_bakery.parallel.executor.SETTINGS.max_concurrency", 5)
        assert resolve_max_workers(-1, n_tasks=10) == 5

    def test_positive_jobs_clamped_when_no_tasks(self):
        assert resolve_max_workers(5, n_tasks=0) == 1


class TestParallelShellExecutor:
    def _executor(self, max_workers, use_live=False):
        # Non-terminal console + use_live=False keeps tests headless and deterministic.
        return ParallelShellExecutor(
            max_workers=max_workers,
            console=Console(file=io.StringIO()),
            use_live=use_live,
        )

    def test_empty_tasks_returns_empty(self):
        assert self._executor(2).run([]) == []

    def test_results_returned_in_input_order(self):
        # Sleep durations are inverted vs. input order so completion order differs.
        durations = {"a": 0.30, "b": 0.05, "c": 0.15}
        tasks = [ShellTask(key=k, cmd=[PY, "-c", f"import time; time.sleep({d})"]) for k, d in durations.items()]
        results = self._executor(3).run(tasks)
        assert [r.task.key for r in results] == ["a", "b", "c"]

    def test_spawn_failure_captured_not_raised(self):
        tasks = [ShellTask(key="x", cmd=["definitely-not-a-real-binary-zzz"])]
        results = self._executor(1).run(tasks)
        assert results[0].returncode is None
        assert isinstance(results[0].exception, Exception)
        assert results[0].ok is False

    def test_env_applied(self):
        cmd = [PY, "-c", "import os,sys; sys.stdout.write(os.environ.get('FOO',''))"]
        tasks = [ShellTask(key="e", cmd=cmd, env={**os.environ, "FOO": "bar"})]
        results = self._executor(1).run(tasks)
        assert results[0].stdout == b"bar"

    def test_cwd_applied(self, tmp_path):
        cmd = [PY, "-c", "import os,sys; sys.stdout.write(os.getcwd())"]
        tasks = [ShellTask(key="d", cmd=cmd, cwd=tmp_path)]
        results = self._executor(1).run(tasks)
        assert results[0].stdout.decode() == str(tmp_path)

    def test_on_result_called_once_per_task_on_main_thread(self):
        tasks = [ShellTask(key=str(i), cmd=[PY, "-c", "pass"]) for i in range(5)]
        seen_keys = []
        seen_threads = set()

        def on_result(result):
            seen_keys.append(result.task.key)
            seen_threads.add(threading.get_ident())

        self._executor(3).run(tasks, on_result=on_result)
        assert sorted(seen_keys) == sorted(t.key for t in tasks)
        assert seen_threads == {threading.main_thread().ident}

    def test_concurrency_bound_not_exceeded(self, tmp_path):
        # Each task writes "<start> <end>" timestamps; assert peak overlap <= max_workers.
        n, workers, sleep = 6, 2, 0.20
        script = (
            "import time,sys; s=time.time(); time.sleep({sleep}); open(sys.argv[1],'w').write(f'{{s}} {{time.time()}}')"
        ).format(sleep=sleep)
        tasks = [ShellTask(key=str(i), cmd=[PY, "-c", script, str(tmp_path / f"{i}.txt")]) for i in range(n)]
        self._executor(workers).run(tasks)

        intervals = []
        for i in range(n):
            start, end = (tmp_path / f"{i}.txt").read_text().split()
            intervals.append((float(start), float(end)))

        events = []
        for start, end in intervals:
            events.append((start, 1))
            events.append((end, -1))
        events.sort()
        peak = running = 0
        for _, delta in events:
            running += delta
            peak = max(peak, running)
        assert peak <= workers

    def test_resolve_use_live_policy(self):
        terminal = Console(file=io.StringIO(), force_terminal=True)
        non_terminal = Console(file=io.StringIO())
        ex_term = ParallelShellExecutor(max_workers=2, console=terminal, use_live=None)
        ex_plain = ParallelShellExecutor(max_workers=2, console=non_terminal, use_live=None)
        assert ex_term._resolve_use_live(2) is True
        assert ex_term._resolve_use_live(1) is False  # single task -> no live table
        assert ex_plain._resolve_use_live(2) is False  # non-terminal -> no live table
