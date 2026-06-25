"""Map a PR's changed files to the image/version build matrix it affects.

The classifier (:func:`classify_changes`) is pure so it can be unit-tested with
synthetic file lists; git I/O lives in :func:`git_changed_files`.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from posit_bakery.config import BakeryConfig
    from posit_bakery.config.image.image import Image


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


# Paths (relative to the bakery context root) that never trigger a build.
_IGNORE_EXACT = {".gitignore", ".pre-commit-config.yaml"}
_IGNORE_PREFIXES = (".idea/", ".claude/", ".github/")
# Paths that conservatively trigger a full build (fail safe).
# NOTE: the _FULL check must run before the _IGNORE check below, because
# ".github/workflows/" is a strict sub-prefix of the ignored ".github/".
_FULL_EXACT = {"bakery.yaml", "bakery.yml"}
_FULL_PREFIXES = (".github/workflows/",)


@dataclass
class ImageChangeSet:
    """What to build for a single image, derived from a PR's changed files."""

    versions: set[str] = field(default_factory=set)
    include_all_release: bool = False
    include_dev: bool = False
    include_matrix_latest: bool = False

    @property
    def empty(self) -> bool:
        return not (self.versions or self.include_all_release or self.include_dev or self.include_matrix_latest)


@dataclass
class MatrixSelection:
    """The full result of classifying a changeset.

    ``full`` means "build everything per the caller's normal flags" (the
    fail-safe / unrecognized-change fallback). Otherwise ``images`` maps image
    name -> the subset to build.
    """

    full: bool = False
    images: dict[str, ImageChangeSet] = field(default_factory=dict)

    def for_image(self, name: str) -> ImageChangeSet:
        return self.images.setdefault(name, ImageChangeSet())


def _attribute(cs: ImageChangeSet, image: "Image", remainder: str) -> None:
    """Update an image's change set for a path under that image's directory.

    ``remainder`` is the path relative to the image directory ("" for the
    directory itself).
    """
    has_dev = bool(image.devVersions)

    if image.matrix is not None:
        # Matrix images: any attributed change exercises the latest slice, plus
        # dev versions when declared.
        cs.include_matrix_latest = True
        cs.include_dev = cs.include_dev or has_dev
        return

    if remainder == "template" or remainder.startswith("template/"):
        cs.include_dev = cs.include_dev or has_dev
        return

    first_segment = remainder.split("/", 1)[0] if remainder else ""
    matched_version = False
    for version in image.versions:
        if version.subpath == first_segment:
            cs.versions.add(version.name)
            matched_version = True
    if matched_version:
        return

    # Image-root file or unrecognized subdirectory: fail safe to all release versions.
    cs.include_all_release = True


def classify_changes(config: "BakeryConfig", changed_files: Iterable[str]) -> MatrixSelection:
    """Classify changed file paths (relative to the bakery context) into a build selection."""
    selection = MatrixSelection()
    base = config.base_path

    # (relative-posix-image-dir, Image) pairs, computed once.
    image_dirs: list[tuple[str, "Image"]] = []
    for image in config.model.images:
        rel = PurePosixPath(image.path.relative_to(base)).as_posix()
        image_dirs.append((rel, image))

    for raw in changed_files:
        path = PurePosixPath(raw).as_posix()

        if path.lower().endswith(".md"):
            continue
        if path in _FULL_EXACT or path.startswith(_FULL_PREFIXES):
            selection.full = True
            continue
        if path in _IGNORE_EXACT or path.startswith(_IGNORE_PREFIXES):
            continue

        matched = False
        for rel, image in image_dirs:
            prefix = rel + "/"
            if path == rel or path.startswith(prefix):
                remainder = path[len(prefix) :] if path.startswith(prefix) else ""
                _attribute(selection.for_image(image.name), image, remainder)
                matched = True
                break
        if matched:
            continue

        # Not Markdown, not ignored, not attributable -> fail safe.
        selection.full = True

    selection.images = {name: cs for name, cs in selection.images.items() if not cs.empty}
    return selection
