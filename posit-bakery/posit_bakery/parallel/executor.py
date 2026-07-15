from __future__ import annotations

import logging
import os
import queue
import signal
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from posit_bakery.const import DEFAULT_COMMAND_TIMEOUT_SECONDS
from posit_bakery.log import stderr_console
from posit_bakery.settings import SETTINGS

# Grace period (seconds) to let a SIGTERM'd child group exit cleanly — e.g. dgoss removing
# its container via its EXIT trap — before we escalate to SIGKILL.
TERMINATE_GRACE_SECONDS = 10.0

# Slice width for CommandRunner.sleep()'s interruptible backoff wait. Short
# enough that a shutdown request is noticed promptly without busy-waiting.
RETRY_SLEEP_SLICE_SECONDS = 0.5

log = logging.getLogger(__name__)

# Holds the current worker slot number (1..max_workers) for whichever pool thread is
# running a task/job, so log records emitted deep inside that call (e.g. from oras.py,
# soci.py) can be traced back to the operation that produced them.
_worker_slot = threading.local()


class _WorkerTagFilter(logging.Filter):
    """Prefixes log records with the emitting thread's worker slot, when it has one."""

    def filter(self, record: logging.LogRecord) -> bool:
        slot = getattr(_worker_slot, "value", None)
        if slot is not None:
            # No square brackets: RichHandler is configured with markup=True, which parses
            # "[...]" as style tags and silently swallows unrecognized ones.
            record.msg = f"w{slot} | {record.msg}"
        return True


def _ensure_worker_tag_filter() -> None:
    """Attach :class:`_WorkerTagFilter` to every root logging handler, once.

    Record-emitting loggers (e.g. in ``oras.py``, ``soci.py``) only run *their own*
    filters before propagating; a filter must sit on the handler itself to see records
    from every logger. Deferred until a pool actually runs (rather than at import time)
    so it always runs after :func:`posit_bakery.log.init_logging` has installed handlers.
    """
    for handler in logging.getLogger().handlers:
        if not any(isinstance(f, _WorkerTagFilter) for f in handler.filters):
            handler.addFilter(_WorkerTagFilter())


class ExecutorInterrupted(Exception):
    """Raised by :meth:`CommandRunner.sleep` when the bound executor's shutdown
    flag flips mid-wait.

    Lets a job blocked in retry backoff unwind within one slice of a shutdown
    request (e.g. Ctrl-C) instead of finishing its full sleep and blocking
    process exit via ThreadPoolExecutor's atexit thread-join.
    """


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
class ShellJob:
    """A unit of work that runs an ordered sequence of commands.

    ``run`` receives a :class:`CommandRunner` bound to this job and uses it to invoke each
    command in order; the executor runs jobs concurrently up to the worker bound. The
    callable's return value is surfaced on :attr:`JobResult.value`.
    """

    key: str
    run: Callable[["CommandRunner"], Any]
    label: str | None = None
    payload: Any = None  # opaque caller data, passed through unchanged on JobResult.job.payload

    @property
    def display_label(self) -> str:
        """Human-facing label for live output; falls back to job key."""
        return self.label or self.key


@dataclass
class JobResult:
    """The outcome of running a ShellJob."""

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


class PrefixedLogSink:
    """Thread-safe console sink for interleaved concurrent output, prefixed per key.

    Each `write()` call is expected to be one complete line (e.g. one line yielded by
    `python_on_whales`'s ``stream_logs``), so a single lock around the print is enough to
    keep concurrent writers from interleaving mid-line.
    """

    def __init__(self, console: Console = stderr_console) -> None:
        self._console = console
        self._lock = threading.Lock()

    def write(self, key: str, line: str) -> None:
        """Print `line` prefixed with `[key]`, guarded by a lock shared across all keys."""
        with self._lock:
            self._console.file.write(f"[{key}] {line}\n")


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

    def _mark_running_row(self, key: str, label: str) -> None:
        """Flip a live-table row from queued to running and start its timer.

        Safe to call from worker threads: Rich Progress mutations are internally locked and
        are not console output. No-op when no live Progress is attached.
        """
        progress = self._progress
        if progress is None:
            return
        row_id = self._progress_ids.get(key)
        if row_id is not None:
            progress.start_task(row_id)
            progress.update(row_id, description=f"[bright_blue]running {label}")

    def _mark_running(self, task: ShellTask) -> None:
        """Flip a task's live-table row from queued to running and start its timer.

        Safe to call from worker threads: Rich Progress mutations are internally locked and
        are not console output. No-op when no live Progress is attached.
        """
        self._mark_running_row(task.key, task.display_label)

    def _spawn_and_communicate(
        self,
        cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        timeout: float | None = None,
        on_started: Callable[[], None] | None = None,
    ) -> tuple[int | None, bytes, bytes, bool, Exception | None]:
        """Spawn a tracked child process and communicate with it, handling timeout and shutdown.

        Spawns a subprocess in a new session (process group), registers it as active, and
        manages its lifecycle: timeout enforcement, graceful termination on interrupt/timeout,
        and tracking for Ctrl-C safety. Calls on_started() just before communicate() blocks.
        Returns (returncode, stdout, stderr, timed_out, exception). exception is set on
        spawn failure (e.g. FileNotFoundError) or on an unhandled timeout/interrupt artifact;
        callers with raise-on-failure semantics check it themselves.
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
            # cannot escape termination. The returned result is discarded as run()/run_jobs() unwinds.
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
        """Run one job's callable, handing it a CommandRunner bound to the job."""
        start = time.monotonic()
        runner = CommandRunner(self, job.key, job.display_label)
        try:
            value = job.run(runner)
        except Exception as exc:  # job callable raised; surface without crashing pool
            return JobResult(job=job, value=None, exception=exc, duration=time.monotonic() - start)
        return JobResult(job=job, value=value, exception=None, duration=time.monotonic() - start)

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
        """Run all tasks, returning results in input order. ``on_result`` fires per task on the main thread.

        On KeyboardInterrupt (or any BaseException) the executor cancels queued tasks and
        terminates in-flight child processes before re-raising, so Ctrl-C is responsive and
        does not leave orphaned children.
        """
        return self._execute_pool(tasks, worker=self._run_one, on_result=on_result)

    def run_jobs(
        self,
        jobs: list[ShellJob],
        *,
        on_result: Callable[[JobResult], None] | None = None,
    ) -> list[JobResult]:
        """Run all jobs (each an ordered command sequence) concurrently, returning results in input order.

        Each job's callable runs on a worker thread with a :class:`CommandRunner` bound to it;
        commands it spawns are tracked exactly like task runs, so timeout enforcement,
        process-group termination, and interrupt-safety all apply. ``on_result`` fires per job
        on the main thread (so callers can mutate shared state without locks).
        """
        return self._execute_pool(jobs, worker=self._run_job, on_result=on_result)

    @staticmethod
    def _run_with_slot(worker: Callable[[Any], Any], unit: Any, slot_queue: "queue.SimpleQueue[int]") -> Any:
        """Run ``worker(unit)`` with a worker slot number bound to this thread for the
        duration of the call, so nested log records get tagged by :class:`_WorkerTagFilter`.
        """
        slot = slot_queue.get()
        _worker_slot.value = slot
        try:
            return worker(unit)
        finally:
            del _worker_slot.value
            slot_queue.put(slot)

    def _execute_pool(
        self,
        units: list,
        *,
        worker: Callable[[Any], Any],
        on_result: Callable[[Any], None] | None,
    ) -> list:
        """Shared driver for :meth:`run` and :meth:`run_jobs`.

        ``units`` each expose ``.key`` and ``.display_label``; ``worker`` maps a unit to its
        result, and the result must expose ``.ok`` (used to render live table's check/cross mark).
        Owns the thread pool, live-table lifecycle, interrupt handling, and input-order result
        assembly so both call paths share identical Ctrl-C and process-group-termination semantics.
        """
        if not units:
            return []

        log.info(f"Using {self.max_workers} worker(s) for {len(units)} concurrent operation(s)")
        _ensure_worker_tag_filter()

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
                result = future.result()
                results_by_key[future_map[future].key] = result
                if progress is not None:
                    status = "[green3]✓" if result.ok else "[bright_red]✗"
                    progress.update(
                        progress_ids[future_map[future].key],
                        description=f"{status} {future_map[future].display_label}",
                        completed=1,
                    )
                if on_result is not None:
                    on_result(result)

        slot_queue: queue.SimpleQueue[int] = queue.SimpleQueue()
        for slot in range(1, self.max_workers + 1):
            slot_queue.put(slot)

        pool = ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            if progress is not None:
                with progress:
                    for unit in units:
                        progress_ids[unit.key] = progress.add_task(
                            f"[quiet]{'queued':<7} {unit.display_label}", total=1, start=False
                        )
                    self._progress_ids = progress_ids
                    future_map = {pool.submit(self._run_with_slot, worker, unit, slot_queue): unit for unit in units}
                    consume(future_map)
            else:
                future_map = {pool.submit(self._run_with_slot, worker, unit, slot_queue): unit for unit in units}
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
    """Executes commands within a ShellJob, binding subprocess lifecycle to the job's executor.

    Each job receives a CommandRunner instance bound to itself; the runner's ``run()`` method
    spawns subprocesses via the shared executor's tracked-spawn primitives, so timeout
    enforcement, process-group termination, and interrupt-safety all apply transparently.
    """

    def __init__(self, executor: "ParallelShellExecutor", key: str, label: str | None = None) -> None:
        self._executor = executor
        self._key = key
        self._label = label or key

    def run(
        self,
        cmd: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
        timeout: float | None = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    ) -> subprocess.CompletedProcess:
        """Run ``cmd`` as a tracked child process and return completed result.

        Does not raise on non-zero exit — callers with raise-on-failure semantics
        (e.g. ``OrasCommand.run()``) check ``returncode`` themselves, exactly as when
        calling ``subprocess.run()`` directly.

        :param timeout: Seconds to allow before killing the child; defaults to
            :data:`DEFAULT_COMMAND_TIMEOUT_SECONDS` so a hung ``oras``/``soci`` call
            can't block a publish run forever. Pass ``None`` for no bound.
        """
        returncode, stdout, stderr, _timed_out, exception = self._executor._spawn_and_communicate(
            cmd,
            env=env,
            cwd=cwd,
            timeout=timeout,
            on_started=lambda: self._executor._mark_running_row(self._key, self._label),
        )
        if exception is not None:
            raise exception
        return subprocess.CompletedProcess(args=cmd, returncode=returncode, stdout=stdout, stderr=stderr)

    def sleep(self, seconds: float, *, slice_seconds: float = RETRY_SLEEP_SLICE_SECONDS) -> None:
        """Sleep for ``seconds``, waking early to raise :class:`ExecutorInterrupted`
        if the bound executor's shutdown flag flips mid-wait.

        Passed as the ``sleep`` callable to
        :func:`posit_bakery.retry.retry_on_transient` when retrying inside a
        parallel job, so a job blocked in backoff notices a shutdown request
        within one slice instead of blocking process exit.
        """
        remaining = seconds
        while remaining > 0:
            if self._executor._shutdown:
                raise ExecutorInterrupted(f"shutdown requested during backoff for '{self._key}'")
            time.sleep(min(slice_seconds, remaining))
            remaining -= slice_seconds
        if self._executor._shutdown:
            raise ExecutorInterrupted(f"shutdown requested during backoff for '{self._key}'")
