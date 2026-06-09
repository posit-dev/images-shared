from __future__ import annotations

import logging
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from posit_bakery.log import stderr_console
from posit_bakery.settings import SETTINGS


@dataclass
class ShellTask:
    """A single subprocess invocation to run in parallel."""

    key: str
    cmd: list[str]
    env: dict[str, str] | None = None
    cwd: Path | None = None
    label: str | None = None
    payload: Any = None  # opaque caller data, passed through unchanged to ShellResult.task.payload

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

    def _resolve_use_live(self, n_tasks: int) -> bool:
        """Decide whether to render a live table: explicit override, else TTY + not quiet + >1 task."""
        if self._use_live is not None:
            return self._use_live
        return self.console.is_terminal and SETTINGS.log_level < logging.ERROR and n_tasks > 1

    def _run_one(self, task: ShellTask) -> ShellResult:
        """Run a single task's subprocess, capturing output and any spawn failure."""
        start = time.monotonic()
        try:
            completed = subprocess.run(task.cmd, env=task.env, cwd=task.cwd, capture_output=True)
            return ShellResult(
                task=task,
                returncode=completed.returncode,
                stdout=completed.stdout,
                stderr=completed.stderr,
                duration=time.monotonic() - start,
            )
        except Exception as exc:  # spawn failures (FileNotFoundError, PermissionError, ...)
            return ShellResult(
                task=task,
                returncode=None,
                stdout=b"",
                stderr=b"",
                duration=time.monotonic() - start,
                exception=exc,
            )

    def run(
        self,
        tasks: list[ShellTask],
        *,
        on_result: Callable[[ShellResult], None] | None = None,
    ) -> list[ShellResult]:
        """Run all tasks, returning results in input order. ``on_result`` fires per task on the main thread."""
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

        def drain() -> None:
            with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
                future_map = {pool.submit(self._run_one, task): task for task in tasks}
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

        if progress is not None:
            with progress:
                for task in tasks:
                    progress_ids[task.key] = progress.add_task(f"[quiet]queued {task.display_label}", total=1)
                drain()
        else:
            drain()

        return [results_by_key[task.key] for task in tasks]
