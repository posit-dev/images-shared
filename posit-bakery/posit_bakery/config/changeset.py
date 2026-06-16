"""Map a PR's changed files to the image/version build matrix it affects.

The classifier (:func:`classify_changes`) is pure so it can be unit-tested with
synthetic file lists; git I/O lives in :func:`git_changed_files`.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def git_changed_files(repo_root: Path, base_ref: str) -> list[str]:
    """Return repo-root-relative POSIX paths changed between the merge-base of
    ``base_ref`` and ``HEAD``.

    Uses three-dot/``--merge-base`` semantics so commits landed on the base
    branch after this branch diverged are not counted.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "diff", "--name-only", "--merge-base", base_ref, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]
