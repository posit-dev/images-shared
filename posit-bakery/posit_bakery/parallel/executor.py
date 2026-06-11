from __future__ import annotations

import logging
import os
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from posit_bakery.log import stderr_console
from posit_bakery.settings import SETTINGS

if TYPE_CHECKING:
    from posit_bakery.parallel.retry import RetryPolicy

# Grace period (seconds) to let a SIGTERM'd child group exit cleanly — e.g. dgoss removing
# its container via its EXIT trap — before we escalate to SIGKILL.
TERMINATE_GRACE_SECONDS = 10.0


def _signal_process_group(proc: subprocess.Popen, sig: int) -> None:
    """Send `sig` to the child's whole process group, so a wrapper (e.g. dgoss) and the
    processes it spawned (e.g. docker) are all signalled together. Falls back to signalling
    just the process where process groups are unavailable (non-POSIX) or the child is already
    gone. Best-effort: never raises.
    """
    try:
        os.killpg(os.getpgid(proc.pid), sig)
    except (ProcessLookupError, PermissionError, OSError, AttributeError):
        try:
            proc.send_signal(sig)
        except Exception:
            pass


@dataclass
class ShellTask:
    """A single subprocess invocation to run in parallel."""

    key: str
    cmd: list[str]
    env: dict[str, str] | None = None
    cwd: Path | None = None
    label: str | None = None
    payload: Any = None  # opaque caller data, passed through unchanged to ShellResult.task.payload
    timeout: float | None = None  # seconds; None or <=0 means no timeout (enforced by the caller)

    @property
    def display_label(self) -> str:
        """Human-facing label for live output; falls back to the task key."""
        return self.label or self.key


@dataclass
class ShellResult:
    """The outcome of running a ShellTask."""

    task: ShellTask
    returncode: int | None
    stdout: bytes
    stderr: bytes
    duration: float
    exception: Exception | None = None
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        """True when the process spawned and exited zero."""
        return self.exception is None and self.returncode == 0


@dataclass
class CommandResult:
    """The outcome of a single command run through a :class:`CommandRunner`.

    Unlike :class:`ShellResult` (one task = one command), this is the per-command result a
    multi-step job sees, so a job can branch on each step's outcome before running the next.
    """

    cmd: list[str]
    returncode: int | None
    stdout: bytes
    stderr: bytes
    duration: float
    timed_out: bool = False
    exception: Exception | None = None

    @property
    def ok(self) -> bool:
        """True when the process spawned and exited zero."""
        return self.exception is None and self.returncode == 0


@dataclass
class ShellJob:
    """A unit of work that runs an ordered sequence of commands.

    ``run`` receives a :class:`CommandRunner` bound to this job and uses it to invoke each
    command in order; the executor runs jobs concurrently up to the worker bound. The
    callable's return value is surfaced on :attr:`JobResult.value`.

    ``retry`` and ``command_timeout`` are the default policy the bound runner applies to every
    command the job runs (a command may still override them per call), so a job declares its
    flakiness/timeout handling once rather than threading it through each step.
    """

    key: str
    run: Callable[["CommandRunner"], Any]
    label: str | None = None
    payload: Any = None  # opaque caller data, passed through unchanged to JobResult.job.payload
    retry: "RetryPolicy | None" = None
    command_timeout: float | None = None

    @property
    def display_label(self) -> str:
        """Human-facing label for live output; falls back to the job key."""
        return self.label or self.key


@dataclass
class JobResult:
    """The outcome of running a :class:`ShellJob`."""

    job: ShellJob
    value: Any = None
    exception: Exception | None = None
    duration: float = 0.0

    @property
    def ok(self) -> bool:
        """True when the job callable returned without raising."""
        return self.exception is None


def resolve_max_workers(jobs: int | None, n_tasks: int) -> int:
    """Resolve the worker count: --jobs override, else SETTINGS, clamped to [1, n_tasks].

    :param jobs: Explicit override (e.g. from a --jobs CLI flag). Ignored when not positive.
    :param n_tasks: Number of tasks to run; the result never exceeds this (but is at least 1).
    """
    workers = jobs if (jobs is not None and jobs > 0) else SETTINGS.max_concurrency
    workers = max(1, workers)
    return min(workers, max(1, n_tasks))


class ParallelShellExecutor:
    """Run ShellTasks concurrently with bounded workers and an optional Rich live table.

    Worker threads only run their subprocess and return captured bytes — they never touch
    the logger or console. The main thread drains completions, drives the live table, and
    invokes ``on_result`` (so callers mutate shared state without locks).
    """

    def __init__(
        self,
        *,
        max_workers: int,
        console: Console = stderr_console,
        use_live: bool | None = None,
    ) -> None:
        self.max_workers = max(1, max_workers)
        self.console = console
        self._use_live = use_live
        self._active: set[subprocess.Popen] = set()
        self._lock = threading.Lock()
        self._shutdown = False
        self._progress: Progress | None = None
        self._progress_ids: dict[str, Any] = {}

    def _resolve_use_live(self, n_tasks: int) -> bool:
        """Decide whether to render a live table: explicit override, else TTY + not quiet + >1 task."""
        if self._use_live is not None:
            return self._use_live
        return self.console.is_terminal and SETTINGS.log_level < logging.ERROR and n_tasks > 1

    def _mark_running(self, task: ShellTask) -> None:
        """Flip a task's live-table row from queued to running and start its timer.

        Safe to call from worker threads: Rich Progress mutations are internally locked and
        are not console output. No-op when no live Progress is attached.
        """
        progress = self._progress
        if progress is None:
            return
        task_id = self._progress_ids.get(task.key)
        if task_id is not None:
            progress.start_task(task_id)
            progress.update(task_id, description=f"[bright_blue]running {task.display_label}")

    def _spawn_and_communicate(
        self,
        cmd: list[str],
        *,
        env: dict[str, str] | None,
        cwd: Path | None,
        timeout: float | None,
        on_started: Callable[[], None] | None = None,
    ) -> tuple[int | None, bytes, bytes, bool, Exception | None]:
        """Spawn ``cmd`` as a tracked child process group, enforcing ``timeout`` if set.

        The single point where this executor launches subprocesses, so both the one-task path
        and multi-step jobs share the same registration, timeout, and interrupt-safety logic.
        Honors the shutdown race: a child spawned after an interrupt began is stopped at once.
        ``on_started`` (if given) fires after the child is registered, before it is awaited.

        :returns: ``(returncode, stdout, stderr, timed_out, exception)``. On spawn failure,
            ``returncode`` is ``None`` and ``exception`` is set.
        """
        try:
            proc = subprocess.Popen(
                cmd,
                env=env,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except Exception as exc:  # spawn failures (FileNotFoundError, PermissionError, ...)
            return None, b"", b"", False, exc

        with self._lock:
            if self._shutdown:
                interrupted = True
            else:
                self._active.add(proc)
                interrupted = False
        if interrupted:
            # An interrupt began before this child was registered; stop it now so it
            # cannot escape termination. The returned result is discarded as run() unwinds.
            self._stop(proc)
            stdout, stderr = proc.communicate()
            return proc.returncode, stdout or b"", stderr or b"", False, None

        if on_started is not None:
            on_started()
        timed_out = False
        exception: Exception | None = None
        eff_timeout = timeout if (timeout is not None and timeout > 0) else None
        try:
            try:
                stdout, stderr = proc.communicate(timeout=eff_timeout)
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                exception = exc
                self._stop(proc)
                stdout, stderr = proc.communicate()  # reap remaining output after the child exits
        finally:
            with self._lock:
                self._active.discard(proc)

        return proc.returncode, stdout or b"", stderr or b"", timed_out, exception

    def _run_one(self, task: ShellTask) -> ShellResult:
        """Run one task as a tracked child process, enforcing task.timeout if set."""
        start = time.monotonic()
        returncode, stdout, stderr, timed_out, exception = self._spawn_and_communicate(
            task.cmd,
            env=task.env,
            cwd=task.cwd,
            timeout=task.timeout,
            on_started=lambda: self._mark_running(task),
        )
        return ShellResult(
            task=task,
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
            duration=time.monotonic() - start,
            exception=exception,
            timed_out=timed_out,
        )

    def _run_job(self, job: ShellJob) -> JobResult:
        """Run one job's callable, handing it a CommandRunner bound to this job."""
        start = time.monotonic()
        runner = CommandRunner(
            self,
            job.key,
            job.display_label,
            default_retry=job.retry,
            default_timeout=job.command_timeout,
        )
        try:
            value = job.run(runner)
        except Exception as exc:  # job glue raised; surface it without crashing the pool
            return JobResult(job=job, value=None, exception=exc, duration=time.monotonic() - start)
        return JobResult(job=job, value=value, exception=None, duration=time.monotonic() - start)

    def _mark_step(self, key: str, label: str, step_label: str | None, attempt: int) -> None:
        """Update a job's live-table row to show the command/step it is currently running.

        Safe to call from worker threads (Rich Progress mutations are internally locked).
        No-op when no live Progress is attached.
        """
        progress = self._progress
        if progress is None:
            return
        task_id = self._progress_ids.get(key)
        if task_id is None:
            return
        progress.start_task(task_id)
        description = f"[bright_blue]running {label}"
        if step_label:
            description += f" — {step_label}"
        if attempt > 1:
            description += f" (retry {attempt})"
        progress.update(task_id, description=description)

    @staticmethod
    def _stop(proc: subprocess.Popen, grace: float = TERMINATE_GRACE_SECONDS) -> None:
        """Stop a child group gracefully: SIGTERM the group, wait up to grace, then SIGKILL it."""
        _signal_process_group(proc, signal.SIGTERM)
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            _signal_process_group(proc, signal.SIGKILL)

    def _terminate_active(self, grace: float = TERMINATE_GRACE_SECONDS) -> None:
        """Terminate every in-flight child group: SIGTERM all, then SIGKILL stragglers after a shared grace window."""
        with self._lock:
            procs = list(self._active)
        for proc in procs:
            _signal_process_group(proc, signal.SIGTERM)
        deadline = time.monotonic() + grace
        for proc in procs:
            try:
                proc.wait(timeout=max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                _signal_process_group(proc, signal.SIGKILL)
            except Exception:
                pass

    def run(
        self,
        tasks: list[ShellTask],
        *,
        on_result: Callable[[ShellResult], None] | None = None,
    ) -> list[ShellResult]:
        """Run all tasks (one command each), returning results in input order.

        ``on_result`` fires per task on the main thread. On KeyboardInterrupt (or any
        BaseException) queued tasks are cancelled and in-flight children terminated before
        re-raising, so Ctrl-C is responsive and does not leave orphaned children.
        """
        return self._execute_pool(tasks, worker=self._run_one, ok_of=lambda r: r.ok, on_result=on_result)

    def run_jobs(
        self,
        jobs: list[ShellJob],
        *,
        on_result: Callable[[JobResult], None] | None = None,
    ) -> list[JobResult]:
        """Run all jobs (each an ordered command sequence) concurrently, results in input order.

        Each job's callable runs on a worker thread with a :class:`CommandRunner` bound to it;
        the commands it spawns are tracked exactly like one-task runs, so timeout enforcement,
        process-group termination, and interrupt-safety all apply. ``on_result`` fires per job
        on the main thread (so callers mutate shared state without locks).
        """
        return self._execute_pool(jobs, worker=self._run_job, ok_of=lambda r: r.ok, on_result=on_result)

    def _execute_pool(
        self,
        units: list,
        *,
        worker: Callable[[Any], Any],
        ok_of: Callable[[Any], bool],
        on_result: Callable[[Any], None] | None,
    ) -> list:
        """Shared driver for :meth:`run` and :meth:`run_jobs`.

        ``units`` each expose ``.key`` and ``.display_label``; ``worker`` maps a unit to its
        result and ``ok_of`` reports success for the live table's ✓/✗. Owns the thread pool,
        live-table lifecycle, interrupt handling, and input-order result assembly.
        """
        if not units:
            return []

        self._shutdown = False
        self._progress = None
        self._progress_ids = {}
        use_live = self._resolve_use_live(len(units))
        results_by_key: dict[str, Any] = {}
        progress: Progress | None = None
        progress_ids: dict[str, Any] = {}

        if use_live:
            progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
                console=self.console,
                transient=False,
            )
            self._progress = progress

        def consume(future_map: dict) -> None:
            for future in as_completed(future_map):
                unit = future_map[future]
                result = future.result()
                results_by_key[unit.key] = result
                if progress is not None:
                    status = "[green3]✓" if ok_of(result) else "[bright_red]✗"
                    progress.update(
                        progress_ids[unit.key],
                        description=f"{status} {unit.display_label}",
                        completed=1,
                    )
                if on_result is not None:
                    on_result(result)

        pool = ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            if progress is not None:
                with progress:
                    for unit in units:
                        progress_ids[unit.key] = progress.add_task(
                            f"[quiet]{'queued':<7} {unit.display_label}", total=1, start=False
                        )
                    self._progress_ids = progress_ids
                    future_map = {pool.submit(worker, unit): unit for unit in units}
                    consume(future_map)
            else:
                future_map = {pool.submit(worker, unit): unit for unit in units}
                consume(future_map)
        except BaseException:
            # Interrupted (e.g. Ctrl-C): stop accepting/continuing work, drop queued units,
            # and terminate running children, then propagate.
            with self._lock:
                self._shutdown = True
            pool.shutdown(wait=False, cancel_futures=True)
            self._terminate_active()
            raise
        else:
            pool.shutdown(wait=True)
        finally:
            self._progress = None
            self._progress_ids = {}

        return [results_by_key[unit.key] for unit in units]


class CommandRunner:
    """Per-job handle for running commands as tracked child processes, with optional retry.

    Handed to a :class:`ShellJob`'s callable. Each :meth:`run` spawns through the owning
    executor's tracked-spawn primitive (so timeout, process-group termination, and the
    shutdown race all apply) and, when a :class:`RetryPolicy` is supplied, re-runs on
    retryable failures with exponential backoff.
    """

    def __init__(
        self,
        executor: "ParallelShellExecutor",
        key: str,
        label: str | None = None,
        *,
        default_retry: "RetryPolicy | None" = None,
        default_timeout: float | None = None,
    ) -> None:
        self._executor = executor
        self._key = key
        self._label = label or key
        self._default_retry = default_retry
        self._default_timeout = default_timeout

    def run(
        self,
        cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        timeout: float | None = None,
        retry: "RetryPolicy | None" = None,
        step_label: str | None = None,
    ) -> CommandResult:
        """Run ``cmd`` once (or until it succeeds / retries are exhausted) and return the outcome.

        ``timeout`` and ``retry`` fall back to the runner's job-level defaults when not given,
        so most callers only pass ``cmd`` (and optionally ``step_label``).

        :param retry: When set (or defaulted from the job), failed results matching
            ``retry.retry_on`` are retried up to ``retry.max_attempts`` with backoff sleeps.
        :param step_label: Optional label for this step, surfaced on the job's live-table row.
        """
        if retry is None:
            retry = self._default_retry
        if timeout is None:
            timeout = self._default_timeout
        attempt = 0
        while True:
            attempt += 1
            start = time.monotonic()
            current_attempt = attempt
            returncode, stdout, stderr, timed_out, exception = self._executor._spawn_and_communicate(
                cmd,
                env=env,
                cwd=cwd,
                timeout=timeout,
                on_started=lambda a=current_attempt: self._executor._mark_step(self._key, self._label, step_label, a),
            )
            result = CommandResult(
                cmd=cmd,
                returncode=returncode,
                stdout=stdout,
                stderr=stderr,
                duration=time.monotonic() - start,
                timed_out=timed_out,
                exception=exception,
            )
            if retry is not None and retry.should_retry(result, attempt):
                time.sleep(retry.delay_for(attempt))
                continue
            return result
