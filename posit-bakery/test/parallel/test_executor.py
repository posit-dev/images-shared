import glob
import io
import os
import signal
import sys
import tempfile
import threading
import time

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


class TestParallelShellExecutorTimeout:
    def _executor(self, max_workers):
        return ParallelShellExecutor(max_workers=max_workers, console=Console(file=io.StringIO()), use_live=False)

    def test_timeout_marks_result(self):
        # Sleeps 5s but times out at 0.3s -> killed, flagged timed_out, not raised.
        tasks = [ShellTask(key="t", cmd=[sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.3)]
        start = time.monotonic()
        results = self._executor(1).run(tasks)
        elapsed = time.monotonic() - start
        assert results[0].timed_out is True
        assert results[0].ok is False
        assert results[0].returncode != 0
        assert elapsed < 4  # killed well before the 5s sleep would finish

    def test_no_timeout_when_none(self):
        tasks = [ShellTask(key="t", cmd=[sys.executable, "-c", "pass"], timeout=None)]
        results = self._executor(1).run(tasks)
        assert results[0].timed_out is False
        assert results[0].ok is True

    def test_timeout_terminates_whole_process_group(self, tmp_path):
        import time as _t

        hb = tmp_path / "heartbeat"
        grandchild_src = (
            "import time\n"
            f"i = 0\n"
            f"while True:\n"
            f"    open({str(hb)!r}, 'w').write(str(i))\n"
            f"    i += 1\n"
            f"    time.sleep(0.05)\n"
        )
        # Parent spawns the grandchild (which inherits the parent's new session/process group)
        # and waits on it. If only the parent were killed, the reparented grandchild would keep
        # writing the heartbeat; killing the whole group stops it.
        parent_src = "import subprocess, sys\ng = subprocess.Popen([sys.executable, '-c', sys.argv[1]])\ng.wait()\n"
        tasks = [ShellTask(key="t", cmd=[sys.executable, "-c", parent_src, grandchild_src], timeout=0.5)]
        self._executor(1).run(tasks)

        _t.sleep(0.3)
        v1 = hb.read_text()
        _t.sleep(0.5)
        v2 = hb.read_text()
        assert v1 == v2  # grandchild stopped writing -> the entire process group was terminated


class TestParallelShellExecutorInterrupt:
    def test_sigint_cancels_queued_and_terminates_running(self, tmp_path):
        # 8 tasks, 2 workers, each writes a start marker then sleeps 3s then an end marker.
        # SIGINT fires 0.3s in. Expect: KeyboardInterrupt raised, no task reaches its end
        # marker (running ones killed), not all started (queued ones cancelled), returns fast.
        script = "import sys,time;open(sys.argv[1],'w').close();time.sleep(3);open(sys.argv[2],'w').close()"
        tasks = [
            ShellTask(key=str(i), cmd=[sys.executable, "-c", script, str(tmp_path / f"s{i}"), str(tmp_path / f"e{i}")])
            for i in range(8)
        ]

        def fire():
            time.sleep(0.3)
            os.kill(os.getpid(), signal.SIGINT)

        threading.Thread(target=fire, daemon=True).start()
        ex = ParallelShellExecutor(max_workers=2, console=Console(file=io.StringIO()), use_live=False)
        start = time.monotonic()
        interrupted = False
        try:
            ex.run(tasks)
        except KeyboardInterrupt:
            interrupted = True
        elapsed = time.monotonic() - start

        started = len(glob.glob(str(tmp_path / "s*")))
        ended = len(glob.glob(str(tmp_path / "e*")))
        assert interrupted is True
        assert ended == 0  # nothing ran to completion (running tasks were killed)
        assert started < 8  # queued tasks were cancelled, not launched
        assert elapsed < 3  # returned promptly, did not drain the full queue
