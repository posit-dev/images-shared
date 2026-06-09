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
from typing import Any, Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from posit_bakery.log import stderr_console
from posit_bakery.settings import SETTINGS

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

    def _resolve_use_live(self, n_tasks: int) -> bool:
        """Decide whether to render a live table: explicit override, else TTY + not quiet + >1 task."""
        if self._use_live is not None:
            return self._use_live
        return self.console.is_terminal and SETTINGS.log_level < logging.ERROR and n_tasks > 1

    def _run_one(self, task: ShellTask) -> ShellResult:
        """Run one task as a tracked child process, enforcing task.timeout if set."""
        start = time.monotonic()
        try:
            proc = subprocess.Popen(
                task.cmd,
                env=task.env,
                cwd=task.cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except Exception as exc:  # spawn failures (FileNotFoundError, PermissionError, ...)
            return ShellResult(
                task=task, returncode=None, stdout=b"", stderr=b"", duration=time.monotonic() - start, exception=exc
            )

        with self._lock:
            self._active.add(proc)
        timed_out = False
        exception: Exception | None = None
        timeout = task.timeout if (task.timeout is not None and task.timeout > 0) else None
        try:
            try:
                stdout, stderr = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired as exc:
                timed_out = True
                exception = exc
                self._stop(proc)
                stdout, stderr = proc.communicate()  # reap remaining output after the child exits
        finally:
            with self._lock:
                self._active.discard(proc)

        return ShellResult(
            task=task,
            returncode=proc.returncode,
            stdout=stdout or b"",
            stderr=stderr or b"",
            duration=time.monotonic() - start,
            exception=exception,
            timed_out=timed_out,
        )

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
        if not tasks:
            return []

        use_live = self._resolve_use_live(len(tasks))
        results_by_key: dict[str, ShellResult] = {}
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

        def consume(future_map: dict) -> None:
            for future in as_completed(future_map):
                result = future.result()
                results_by_key[result.task.key] = result
                if progress is not None:
                    status = "[green3]✓" if result.ok else "[bright_red]✗"
                    progress.update(
                        progress_ids[result.task.key],
                        description=f"{status} {result.task.display_label}",
                        completed=1,
                    )
                if on_result is not None:
                    on_result(result)

        pool = ThreadPoolExecutor(max_workers=self.max_workers)
        try:
            if progress is not None:
                with progress:
                    for task in tasks:
                        progress_ids[task.key] = progress.add_task(f"[quiet]queued {task.display_label}", total=1)
                    future_map = {pool.submit(self._run_one, task): task for task in tasks}
                    consume(future_map)
            else:
                future_map = {pool.submit(self._run_one, task): task for task in tasks}
                consume(future_map)
        except BaseException:
            # Interrupted (e.g. Ctrl-C): drop queued tasks and stop running children, then propagate.
            pool.shutdown(wait=False, cancel_futures=True)
            self._terminate_active()
            raise
        else:
            pool.shutdown(wait=True)

        return [results_by_key[task.key] for task in tasks]
