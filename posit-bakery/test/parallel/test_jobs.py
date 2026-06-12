import io
import os
import signal
import sys
import threading
import time

import pytest
from rich.console import Console

from posit_bakery.parallel import (
    CommandResult,
    CommandRunner,
    JobResult,
    ParallelShellExecutor,
    RetryPolicy,
    ShellJob,
)

PY = sys.executable

pytestmark = [pytest.mark.unit]


# A command that fails (exit 1, "transient" stderr) for the first N invocations tracked in a
# counter file, then succeeds (exit 0, stdout "ok"). Lets us drive retry with real subprocesses.
_FLAKY_SRC = (
    "import sys\n"
    "p, fail_until = sys.argv[1], int(sys.argv[2])\n"
    "try:\n"
    "    n = int(open(p).read())\n"
    "except Exception:\n"
    "    n = 0\n"
    "open(p, 'w').write(str(n + 1))\n"
    "if n < fail_until:\n"
    "    sys.stderr.write('error: manifest not found')\n"
    "    sys.exit(1)\n"
    "sys.stdout.write('ok')\n"
)


def _flaky_cmd(counter_path, fail_until):
    return [PY, "-c", _FLAKY_SRC, str(counter_path), str(fail_until)]


def _transient(result):
    return b"not found" in result.stderr.lower()


class TestCommandResult:
    def test_ok_true_on_zero_exit_no_exception(self):
        assert CommandResult(cmd=["true"], returncode=0, stdout=b"", stderr=b"", duration=0.0).ok is True

    def test_ok_false_on_nonzero_exit(self):
        assert CommandResult(cmd=["false"], returncode=1, stdout=b"", stderr=b"", duration=0.0).ok is False

    def test_ok_false_on_exception(self):
        result = CommandResult(
            cmd=["nope"], returncode=None, stdout=b"", stderr=b"", duration=0.0, exception=FileNotFoundError()
        )
        assert result.ok is False


class TestCommandRunner:
    def _executor(self):
        return ParallelShellExecutor(max_workers=1, console=Console(file=io.StringIO()), use_live=False)

    def _runner(self):
        return CommandRunner(self._executor(), key="job", label="job")

    def test_runs_command_and_captures_output(self):
        result = self._runner().run([PY, "-c", "import sys; sys.stdout.write('hi')"])
        assert result.ok is True
        assert result.stdout == b"hi"

    def test_no_retry_returns_first_failure(self, tmp_path, monkeypatch):
        sleeps = []
        monkeypatch.setattr("posit_bakery.parallel.executor.time.sleep", lambda s: sleeps.append(s))
        counter = tmp_path / "c"
        result = self._runner().run(_flaky_cmd(counter, fail_until=5))
        assert result.ok is False
        assert counter.read_text() == "1"  # ran exactly once, no retries
        assert sleeps == []

    def test_retries_transient_failure_then_succeeds(self, tmp_path, monkeypatch):
        sleeps = []
        monkeypatch.setattr("posit_bakery.parallel.executor.time.sleep", lambda s: sleeps.append(s))
        counter = tmp_path / "c"
        policy = RetryPolicy(max_attempts=5, jitter=False, retry_on=_transient)
        result = self._runner().run(_flaky_cmd(counter, fail_until=2), retry=policy)
        assert result.ok is True
        assert result.stdout == b"ok"
        assert counter.read_text() == "3"  # failed twice, succeeded on the third attempt
        assert sleeps == [2.0, 4.0]  # backoff between the two retries

    def test_exhausts_retries_and_returns_last_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("posit_bakery.parallel.executor.time.sleep", lambda s: None)
        counter = tmp_path / "c"
        policy = RetryPolicy(max_attempts=3, jitter=False, retry_on=_transient)
        result = self._runner().run(_flaky_cmd(counter, fail_until=99), retry=policy)
        assert result.ok is False
        assert counter.read_text() == "3"  # tried exactly max_attempts times

    def test_does_not_retry_non_transient_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("posit_bakery.parallel.executor.time.sleep", lambda s: None)
        counter = tmp_path / "c"
        # Predicate only retries "not found"; this command emits a different error.
        policy = RetryPolicy(max_attempts=5, jitter=False, retry_on=lambda r: b"never-matches" in r.stderr)
        result = self._runner().run(_flaky_cmd(counter, fail_until=99), retry=policy)
        assert result.ok is False
        assert counter.read_text() == "1"


class TestShellJobAndResult:
    def test_job_display_label_defaults_to_key(self):
        job = ShellJob(key="k", run=lambda runner: None)
        assert job.display_label == "k"

    def test_job_result_ok_false_with_exception(self):
        job = ShellJob(key="k", run=lambda runner: None)
        assert JobResult(job=job, exception=RuntimeError()).ok is False

    def test_job_result_ok_true_without_exception(self):
        job = ShellJob(key="k", run=lambda runner: None)
        assert JobResult(job=job, value=42).ok is True


class TestRunJobs:
    def _executor(self, max_workers, use_live=False):
        return ParallelShellExecutor(max_workers=max_workers, console=Console(file=io.StringIO()), use_live=use_live)

    def test_empty_jobs_returns_empty(self):
        assert self._executor(2).run_jobs([]) == []

    def test_results_returned_in_input_order(self):
        durations = {"a": 0.30, "b": 0.05, "c": 0.15}
        jobs = [
            ShellJob(key=k, run=lambda runner, d=d: runner.run([PY, "-c", f"import time; time.sleep({d})"]))
            for k, d in durations.items()
        ]
        results = self._executor(3).run_jobs(jobs)
        assert [r.job.key for r in results] == ["a", "b", "c"]

    def test_callable_return_value_captured(self):
        def job_run(runner):
            r1 = runner.run([PY, "-c", "import sys; sys.stdout.write('a')"])
            r2 = runner.run([PY, "-c", "import sys; sys.stdout.write('b')"])
            return (r1.stdout, r2.stdout)

        jobs = [ShellJob(key="seq", run=job_run)]
        results = self._executor(1).run_jobs(jobs)
        assert results[0].ok is True
        assert results[0].value == (b"a", b"b")

    def test_exception_in_callable_captured_not_raised(self):
        def boom(runner):
            raise RuntimeError("kaboom")

        jobs = [
            ShellJob(key="ok", run=lambda runner: runner.run([PY, "-c", "pass"])),
            ShellJob(key="bad", run=boom),
        ]
        results = self._executor(2).run_jobs(jobs)
        by_key = {r.job.key: r for r in results}
        assert by_key["ok"].ok is True
        assert by_key["bad"].ok is False
        assert isinstance(by_key["bad"].exception, RuntimeError)

    def test_on_result_called_once_per_job_on_main_thread(self):
        jobs = [ShellJob(key=str(i), run=lambda runner: runner.run([PY, "-c", "pass"])) for i in range(5)]
        seen_keys = []
        seen_threads = set()

        def on_result(result):
            seen_keys.append(result.job.key)
            seen_threads.add(threading.get_ident())

        self._executor(3).run_jobs(jobs, on_result=on_result)
        assert sorted(seen_keys) == sorted(j.key for j in jobs)
        assert seen_threads == {threading.main_thread().ident}

    def test_job_retry_default_applied_to_commands(self, tmp_path, monkeypatch):
        # A job declares a retry policy; commands it runs without an explicit retry inherit it.
        monkeypatch.setattr("posit_bakery.parallel.executor.time.sleep", lambda s: None)
        counter = tmp_path / "c"
        policy = RetryPolicy(max_attempts=5, jitter=False, retry_on=lambda r: b"not found" in r.stderr.lower())

        def job_run(runner):
            return runner.run(_flaky_cmd(counter, fail_until=1))  # no explicit retry -> job default

        jobs = [ShellJob(key="j", run=job_run, retry=policy)]
        results = self._executor(1).run_jobs(jobs)
        assert results[0].ok is True
        assert results[0].value.ok is True
        assert counter.read_text() == "2"  # failed once, retried, succeeded

    def test_sigint_terminates_running_job_children(self, tmp_path):
        # A job runs a 3s sleep via the runner; SIGINT fires 0.3s in. Expect KeyboardInterrupt
        # and prompt return (the in-flight child is terminated, not waited out).
        script = "import sys,time;open(sys.argv[1],'w').close();time.sleep(3);open(sys.argv[2],'w').close()"
        jobs = [
            ShellJob(
                key=str(i),
                run=lambda runner, i=i: runner.run(
                    [PY, "-c", script, str(tmp_path / f"s{i}"), str(tmp_path / f"e{i}")]
                ),
            )
            for i in range(4)
        ]

        def fire():
            time.sleep(0.3)
            os.kill(os.getpid(), signal.SIGINT)

        threading.Thread(target=fire, daemon=True).start()
        ex = self._executor(2)
        start = time.monotonic()
        interrupted = False
        try:
            ex.run_jobs(jobs)
        except KeyboardInterrupt:
            interrupted = True
        elapsed = time.monotonic() - start

        assert interrupted is True
        assert not list(tmp_path.glob("e*"))  # no job ran to completion
        assert elapsed < 3
