"""Compare two rendered version directories and render a markdown comment.

Used by ``bakery create version --diff-against`` to show reviewers what
changed between a newly-created release edition and a previous one, since
both are wholesale re-renders rather than incremental edits. Unrelated to
``config/changeset.py``'s diffing: that module compares one file (bakery.yaml)
across two *commits* to decide what to rebuild; this module compares two
different *paths* that both exist, live, at the same time, to render a
human-readable comment.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


def read_directory_tree(path: Path) -> dict[str, bytes]:
    """Read every file under `path` into {relative_posix_path: raw_bytes}."""
    tree: dict[str, bytes] = {}
    for file_path in path.rglob("*"):
        if file_path.is_file():
            rel = file_path.relative_to(path).as_posix()
            tree[rel] = file_path.read_bytes()
    return tree


@dataclass
class FileDiff:
    path: str
    status: Literal["added", "removed", "modified", "binary"]
    diff_text: str | None


def _is_binary(content: bytes) -> bool:
    if b"\x00" in content:
        return True
    try:
        content.decode("utf-8")
    except UnicodeDecodeError:
        return True
    return False


def diff_directories(old_tree: dict[str, bytes], new_tree: dict[str, bytes]) -> list[FileDiff]:
    """Compare two directory trees, pure (no filesystem access).

    Returns one FileDiff per file that differs, sorted by path; identical
    files are omitted entirely.
    """
    results: list[FileDiff] = []
    for path in sorted(set(old_tree) | set(new_tree)):
        old_content = old_tree.get(path)
        new_content = new_tree.get(path)

        if old_content == new_content:
            continue

        if old_content is None:
            status: Literal["added", "removed", "modified"] = "added"
        elif new_content is None:
            status = "removed"
        else:
            status = "modified"

        if _is_binary(old_content or b"") or _is_binary(new_content or b""):
            results.append(FileDiff(path=path, status="binary", diff_text=None))
            continue

        old_lines = (old_content or b"").decode("utf-8").splitlines(keepends=True)
        new_lines = (new_content or b"").decode("utf-8").splitlines(keepends=True)
        diff_text = "".join(
            difflib.unified_diff(old_lines, new_lines, fromfile=f"a/{path}", tofile=f"b/{path}")
        )
        results.append(FileDiff(path=path, status=status, diff_text=diff_text))

    return results


def render_markdown(image_name: str, file_diffs: list[FileDiff], max_chars: int = 20000) -> str:
    """Render one image's PR-comment section.

    Both nesting levels use <details open> rather than plain <details>: the
    diff content should be visible as soon as the comment is opened, not
    hidden behind two layers of clicks. `open` still leaves each section
    individually collapsible. If the fully-rendered structure would exceed
    max_chars, falls back to a flat file list instead -- there's no diff
    content to hide behind a per-file toggle in that case, so there's nothing
    to nest.
    """
    if not file_diffs:
        return (
            f"<details open><summary><code>{image_name}</code></summary>\n\n"
            f"_No differences from previous edition._\n\n"
            f"</details>"
        )

    file_sections = []
    for fd in file_diffs:
        body = "_Binary file changed._" if fd.status == "binary" else f"```diff\n{fd.diff_text}```"
        file_sections.append(f"<details open><summary><code>{fd.path}</code></summary>\n\n{body}\n\n</details>")

    full_body = "\n\n".join(file_sections)
    full_rendered = f"<details open><summary><code>{image_name}</code></summary>\n\n{full_body}\n\n</details>"

    if len(full_rendered) <= max_chars:
        return full_rendered

    flat_lines = [f"- `{fd.path}` ({fd.status})" for fd in file_diffs]
    flat_body = "\n".join(flat_lines)
    return (
        f"<details open><summary><code>{image_name}</code></summary>\n\n"
        f"Diff too large to display in full ({len(file_diffs)} files changed):\n\n"
        f"{flat_body}\n\n</details>"
    )
