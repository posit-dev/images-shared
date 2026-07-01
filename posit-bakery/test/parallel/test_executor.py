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
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from posit_bakery.const import DEFAULT_MAX_CONCURRENCY
from posit_bakery.parallel import (
    CommandRunner,
    JobResult,
    ParallelShellExecutor,
    ShellJob,
    ShellResult,
    ShellTask,
    resolve_max_workers,
)

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

    def test_run_one_marks_row_running(self):
        # When a Progress is attached, _run_one flips its row from queued to running and
        # starts the row's timer. (Completion -> ✓ happens later on the main thread, not here.)
        progress = Progress(
            SpinnerColumn(),
            TextColumn("{task.description}"),
            TimeElapsedColumn(),
            console=Console(file=io.StringIO()),
        )
        ex = ParallelShellExecutor(max_workers=1, console=Console(file=io.StringIO()), use_live=False)
        task = ShellTask(key="k", cmd=[sys.executable, "-c", "pass"], label="my-task")
        task_id = progress.add_task("[quiet]queued  my-task", total=1, start=False)
        ex._progress = progress
        ex._progress_ids = {"k": task_id}

        ex._run_one(task)

        row = progress.tasks[task_id]
        assert row.started is True  # _run_one started the row's timer
        assert "running" in row.description  # row flipped to running

    def test_run_one_no_progress_is_noop(self):
        # With no Progress attached (the default), _run_one must run fine and not error.
        ex = ParallelShellExecutor(max_workers=1, console=Console(file=io.StringIO()), use_live=False)
        result = ex._run_one(ShellTask(key="k", cmd=[sys.executable, "-c", "pass"]))
        assert result.ok is True

    def test_run_live_progress_smoke(self):
        # Force the live path with a terminal-like StringIO console; assert run() still
        # returns ordered, successful results (exercises add_task(start=False) -> running -> done).
        ex = ParallelShellExecutor(
            max_workers=2, console=Console(file=io.StringIO(), force_terminal=True), use_live=True
        )
        tasks = [ShellTask(key=str(i), cmd=[sys.executable, "-c", "pass"]) for i in range(3)]
        results = ex.run(tasks)
        assert [r.task.key for r in results] == ["0", "1", "2"]
        assert all(r.ok for r in results)


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

    def test_terminate_kills_whole_process_group(self, tmp_path):
        # A parent task spawns a grandchild that writes an incrementing heartbeat. We wait until the
        # grandchild is actually writing (readiness) and THEN interrupt -- rather than relying on a
        # fixed timer that races interpreter startup under heavy CI parallelism. If only the parent
        # were signalled, the reparented grandchild would keep writing; terminating the whole process
        # group stops it.
        hb = tmp_path / "heartbeat"
        grandchild_src = (
            "import time\n"
            "i = 0\n"
            "while True:\n"
            f"    open({str(hb)!r}, 'w').write(str(i))\n"
            "    i += 1\n"
            "    time.sleep(0.05)\n"
        )
        parent_src = "import subprocess, sys\ng = subprocess.Popen([sys.executable, '-c', sys.argv[1]])\ng.wait()\n"
        tasks = [ShellTask(key="t", cmd=[sys.executable, "-c", parent_src, grandchild_src])]

        def fire():
            # Wait until the grandchild is up and writing, then interrupt; gating on readiness
            # (rather than a fixed delay) keeps this deterministic under any runner load.
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not hb.exists():
                time.sleep(0.02)
            time.sleep(0.1)  # let the grandchild record a few beats
            os.kill(os.getpid(), signal.SIGINT)

        threading.Thread(target=fire, daemon=True).start()
        try:
            self._executor(1).run(tasks)
        except KeyboardInterrupt:
            pass

        assert hb.exists()  # grandchild started and wrote at least once
        v1 = hb.read_text()
        time.sleep(0.5)
        v2 = hb.read_text()
        assert v1 == v2  # heartbeat frozen -> the whole process group (incl. grandchild) was terminated


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

    def test_run_one_stops_child_when_shutdown_already_started(self):
        # If an interrupt has already flipped the shutdown flag, a child spawned by a
        # straggler worker must be stopped immediately rather than run to completion.
        ex = ParallelShellExecutor(max_workers=1, console=Console(file=io.StringIO()), use_live=False)
        with ex._lock:
            ex._shutdown = True
        task = ShellTask(key="t", cmd=[sys.executable, "-c", "import time; time.sleep(30)"])
        start = time.monotonic()
        result = ex._run_one(task)
        elapsed = time.monotonic() - start
        assert elapsed < 3  # stopped promptly, not waited out for 30s
        assert result.returncode != 0  # the child was signalled, not a clean exit
        assert ex._active == set()  # never registered (or already discarded)


class TestShellJob:
    def test_display_label_defaults_to_key(self):
        job = ShellJob(key="abc", run=lambda runner: None)
        assert job.display_label == "abc"

    def test_display_label_uses_label_when_set(self):
        job = ShellJob(key="abc", run=lambda runner: None, label="My Label")
        assert job.display_label == "My Label"


class TestJobResult:
    def test_ok_true_on_no_exception(self):
        job = ShellJob(key="a", run=lambda runner: None)
        result = JobResult(job=job, value=42)
        assert result.ok is True

    def test_ok_false_on_exception(self):
        job = ShellJob(key="a", run=lambda runner: None)
        result = JobResult(job=job, value=None, exception=RuntimeError("boom"))
        assert result.ok is False


class TestParallelShellExecutorJobs:
    def _executor(self, max_workers):
        return ParallelShellExecutor(
            max_workers=max_workers,
            console=Console(file=io.StringIO()),
            use_live=False,
        )

    def test_empty_jobs_returns_empty(self):
        assert self._executor(2).run_jobs([]) == []

    def test_job_value_is_callable_return(self):
        job = ShellJob(key="a", run=lambda runner: runner.run([PY, "-c", "print('hi')"]).stdout.decode().strip())
        results = self._executor(1).run_jobs([job])
        assert results[0].ok is True
        assert results[0].value == "hi"

    def test_results_returned_in_input_order(self):
        # Sleep durations are inverted vs. input order so completion order differs.
        durations = {"a": 0.30, "b": 0.05, "c": 0.15}

        def make_run(d):
            return lambda runner: runner.run([PY, "-c", f"import time; time.sleep({d})"]).returncode

        jobs = [ShellJob(key=k, run=make_run(d)) for k, d in durations.items()]
        results = self._executor(3).run_jobs(jobs)
        assert [r.job.key for r in results] == ["a", "b", "c"]

    def test_job_exception_isolated_others_still_run(self):
        def boom(runner):
            raise RuntimeError("target blew up")

        def ok(runner):
            return runner.run([PY, "-c", "pass"]).returncode

        jobs = [ShellJob(key="bad", run=boom), ShellJob(key="good", run=ok)]
        results = self._executor(2).run_jobs(jobs)
        by_key = {r.job.key: r for r in results}
        assert by_key["bad"].ok is False
        assert isinstance(by_key["bad"].exception, RuntimeError)
        assert by_key["good"].ok is True
        assert by_key["good"].value == 0

    def test_runner_run_returns_completed_process(self):
        captured = {}

        def run(runner):
            captured["result"] = runner.run([PY, "-c", "import sys; sys.stdout.write('out'); sys.exit(3)"])

        self._executor(1).run_jobs([ShellJob(key="a", run=run)])
        result = captured["result"]
        assert result.returncode == 3
        assert result.stdout == b"out"

    def test_runner_run_spawn_failure_raises(self):
        def run(runner):
            runner.run(["definitely-not-a-real-binary-zzz"])

        results = self._executor(1).run_jobs([ShellJob(key="a", run=run)])
        assert results[0].ok is False
        assert isinstance(results[0].exception, (FileNotFoundError, OSError))

    def test_on_result_called_once_per_job_on_main_thread(self):
        jobs = [ShellJob(key=str(i), run=lambda runner: runner.run([PY, "-c", "pass"]).returncode) for i in range(5)]
        seen_keys = []
        seen_threads = set()

        def on_result(result):
            seen_keys.append(result.job.key)
            seen_threads.add(threading.get_ident())

        self._executor(3).run_jobs(jobs, on_result=on_result)
        assert sorted(seen_keys) == sorted(j.key for j in jobs)
        assert seen_threads == {threading.main_thread().ident}

    def test_sigint_terminates_in_flight_children(self, tmp_path):
        # Mirrors TestParallelShellExecutor.test_sigint_cancels_queued_and_terminates_running
        # for the ShellTask path: confirms run_jobs() shares the same interrupt-safety
        # primitive rather than re-testing every nuance of it.
        marker = tmp_path / "started"
        script = f"import pathlib,time; pathlib.Path({str(marker)!r}).write_text('1'); time.sleep(5)"

        def run(runner):
            runner.run([PY, "-c", script])

        ex = self._executor(1)
        result_holder = {}

        def driver():
            try:
                result_holder["results"] = ex.run_jobs([ShellJob(key="a", run=run)])
            except BaseException as exc:
                result_holder["exc"] = exc

        thread = threading.Thread(target=driver)
        thread.start()
        while not marker.exists():
            time.sleep(0.01)
        with ex._lock:
            ex._shutdown = True
        ex._terminate_active()
        thread.join(timeout=5)
        assert not thread.is_alive()
