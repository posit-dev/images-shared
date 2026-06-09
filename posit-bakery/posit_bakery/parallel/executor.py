from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from posit_bakery.settings import SETTINGS


@dataclass
class ShellTask:
    """A single subprocess invocation to run in parallel."""

    key: str
    cmd: list[str]
    env: dict[str, str] | None = None
    cwd: Path | None = None
    label: str | None = None
    payload: Any = None

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


class ParallelShellExecutor:  # implemented in Task 3
    pass
