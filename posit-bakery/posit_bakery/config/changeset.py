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


def git_show_file(repo_root: Path, ref: str, path: str) -> str:
    """Return the text content of ``path`` (POSIX, relative to ``repo_root``) at ``ref``.

    Raises ``subprocess.CalledProcessError`` if ``ref`` doesn't exist, ``path``
    doesn't exist at ``ref``, or any other git failure — same failure shape as
    :func:`git_changed_files`, left to the caller to handle.
    """
    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{ref}:{path}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _index_by_key(entries: object, key: str) -> dict[str, dict]:
    """Index a list of dicts by one of their string-valued keys, ignoring anything malformed."""
    if not isinstance(entries, list):
        return {}
    return {e[key]: e for e in entries if isinstance(e, dict) and isinstance(e.get(key), str)}


def _dependency_versions(entry: dict) -> list[str]:
    """A DependencyVersions entry serializes as either 'versions: [...]' or,
    for a single version, 'version: x' (see DependencyVersions.serialize_versions)."""
    if "versions" in entry and isinstance(entry["versions"], list):
        return [str(v) for v in entry["versions"]]
    if "version" in entry:
        return [str(entry["version"])]
    return []


def _only_lost_latest(old_version: dict, new_version: dict) -> bool:
    """True if new_version is identical to old_version except old_version had
    latest: true and new_version doesn't (unset or false) -- i.e. this entry
    is purely losing latest to some other entry, with no other change."""
    if not (old_version.get("latest", False) and not new_version.get("latest", False)):
        return False
    old_without_latest = {k: v for k, v in old_version.items() if k != "latest"}
    new_without_latest = {k: v for k, v in new_version.items() if k != "latest"}
    return old_without_latest == new_without_latest


def _classify_versions_diff(cs: ImageChangeSet, old_image: dict, new_image: dict) -> None:
    """Tier 1 (non-matrix): narrow to specific versions, or fail-safe to
    include_all_release for anything outside the versions: list."""
    old_rest = {k: v for k, v in old_image.items() if k != "versions"}
    new_rest = {k: v for k, v in new_image.items() if k != "versions"}
    if old_rest != new_rest:
        cs.include_all_release = True
        return

    old_versions = _index_by_key(old_image.get("versions"), "name")
    new_versions = _index_by_key(new_image.get("versions"), "name")
    for name, new_version in new_versions.items():
        old_version = old_versions.get(name)
        if old_version is None:
            cs.versions.add(name)  # New entry.
            continue
        if old_version == new_version:
            continue  # No change to this entry at all.
        if _only_lost_latest(old_version, new_version):
            continue  # Losing latest to some other entry, nothing else changed on this one.
        cs.versions.add(name)  # Some other field changed (including latest moving onto it).
    # Versions only in old_versions (removed): no signal needed.


def _matrix_needs_rebuild(old_image: dict, new_image: dict) -> bool:
    """Tier 2 (matrix): True if anything changed that isn't purely a removed
    pinned-dependency value. Every "yes" case here resolves to the same
    include_matrix_latest action, so this only needs a boolean answer."""
    old_matrix = old_image.get("matrix")
    new_matrix = new_image.get("matrix")
    if not isinstance(old_matrix, dict) or not isinstance(new_matrix, dict):
        return True

    old_rest_image = {k: v for k, v in old_image.items() if k != "matrix"}
    new_rest_image = {k: v for k, v in new_image.items() if k != "matrix"}
    if old_rest_image != new_rest_image:
        return True

    ignored_matrix_keys = ("dependencies", "dependencyConstraints")
    old_matrix_rest = {k: v for k, v in old_matrix.items() if k not in ignored_matrix_keys}
    new_matrix_rest = {k: v for k, v in new_matrix.items() if k not in ignored_matrix_keys}
    if old_matrix_rest != new_matrix_rest:
        return True

    # dependencyConstraints resolve externally (over time, via a network call) --
    # identical constraint text can resolve to a different concrete set, and
    # different text can resolve to the same set. Any change here is treated
    # as needing a rebuild; there's no way to know from text alone whether
    # it's an addition or removal at the concrete-version level.
    if (old_matrix.get("dependencyConstraints") or []) != (new_matrix.get("dependencyConstraints") or []):
        return True

    old_deps = _index_by_key(old_matrix.get("dependencies"), "dependency")
    new_deps = _index_by_key(new_matrix.get("dependencies"), "dependency")

    for name, new_dep in new_deps.items():
        old_dep = old_deps.get(name)
        if old_dep is None:
            return True  # A whole new dependency axis changes the matrix's shape.
        if set(_dependency_versions(new_dep)) - set(_dependency_versions(old_dep)):
            return True  # At least one value added to this axis.

    if any(name not in new_deps for name in old_deps):
        return True  # A whole dependency axis was removed.

    return False  # Only removed values (or no change) everywhere -> nothing to build.


def classify_bakery_yaml_diff(old_text: str, new_text: str) -> MatrixSelection:
    """Structural diff between two bakery.yaml texts, classified the same way
    _attribute() classifies file paths: narrow to specific images/versions where
    the diff is confidently understood, fail safe (MatrixSelection.full) otherwise.

    Pure: no git or filesystem I/O. Both texts are parsed with the same
    ruamel.yaml settings BakeryConfig itself uses (preserve_quotes), so a
    version string like "3.12" round-trips the same way on both sides.
    """
    selection = MatrixSelection()

    # Local import: ruamel.yaml is only needed on this code path.
    from ruamel.yaml import YAML
    from ruamel.yaml.error import YAMLError

    loader = YAML()
    loader.preserve_quotes = True

    try:
        old_yaml = loader.load(old_text)
        new_yaml = loader.load(new_text)
    except YAMLError:
        selection.full = True
        return selection

    if not isinstance(old_yaml, dict) or not isinstance(new_yaml, dict):
        selection.full = True
        return selection

    old_images = old_yaml.get("images")
    new_images = new_yaml.get("images")
    if not isinstance(old_images, list) or not isinstance(new_images, list):
        selection.full = True
        return selection

    old_top = {k: v for k, v in old_yaml.items() if k != "images"}
    new_top = {k: v for k, v in new_yaml.items() if k != "images"}
    if old_top != new_top:
        # A change outside images[] is genuinely global, not scoped to any image.
        selection.full = True
        return selection

    old_by_name = _index_by_key(old_images, "name")
    new_by_name = _index_by_key(new_images, "name")

    for name, new_image in new_by_name.items():
        old_image = old_by_name.get(name)
        if old_image is None or old_image == new_image:
            continue  # New image (path-based classification already covers its files) or unchanged.

        cs = selection.for_image(name)
        has_dev = bool(new_image.get("devVersions"))

        if "matrix" in new_image or "matrix" in old_image:
            if _matrix_needs_rebuild(old_image, new_image):
                cs.include_matrix_latest = True
                cs.include_dev = cs.include_dev or has_dev
            # else: purely removed pinned-dependency values -> no signal.
        else:
            _classify_versions_diff(cs, old_image, new_image)

    selection.images = {name: cs for name, cs in selection.images.items() if not cs.empty}
    return selection


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
