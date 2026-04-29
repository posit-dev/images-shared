"""Parsed version representation for Posit calver-flavored semver strings.

Provides ``ParsedVersion``, a value type that round-trips the input string,
supports comparison per semver §11, and warns (rather than raising) on
unparseable input.
"""

import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from posit_bakery.config.image.version import ImageVersion

log = logging.getLogger(__name__)

# Anchored grammar:
#   <release>      one or more dot-separated digit groups, minimum two groups
#   -<prerelease>  optional, semver prerelease alphabet
#   +<build>       optional, semver build alphabet
_VERSION_RE = re.compile(
    r"^(?P<release>\d+(?:\.\d+)+)"
    r"(?:-(?P<prerelease>[0-9A-Za-z.-]+))?"
    r"(?:\+(?P<build>[0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True)
class ParsedVersion:
    """A parsed Posit calver/semver version string.

    The original string is preserved verbatim so ``str(parsed) == original``.
    Comparison follows semver §11: release tuples first (zero-padded to equal
    length), then prerelease presence (a version with a prerelease is less
    than the same version without), then prerelease segments. Build metadata
    is preserved in ``original`` but ignored for comparison.
    """

    original: str
    release: tuple[int, ...]
    prerelease: str | None = None
    build: str | None = None

    def __str__(self) -> str:
        return self.original

    @classmethod
    def parse(cls, value: str) -> "ParsedVersion | None":
        """Parse a version string. Returns ``None`` on failure and logs a warning."""
        if not isinstance(value, str):
            log.warning("Unparseable version string: %r", value)
            return None
        match = _VERSION_RE.match(value)
        if match is None:
            log.warning("Unparseable version string: %r", value)
            return None
        release = tuple(int(part) for part in match.group("release").split("."))
        return cls(
            original=value,
            release=release,
            prerelease=match.group("prerelease"),
            build=match.group("build"),
        )

    def _release_key(self, length: int) -> tuple[int, ...]:
        """Zero-pad ``self.release`` to ``length`` for length-tolerant comparison."""
        return self.release + (0,) * (length - len(self.release))

    @staticmethod
    def _prerelease_segment_key(segment: str) -> tuple[int, int | str]:
        """Per semver §11.4.3, numeric segments rank below alphanumeric ones."""
        if segment.isdigit():
            return (0, int(segment))
        return (1, segment)

    def _prerelease_key(self) -> tuple[int, tuple[tuple[int, int | str], ...]]:
        """Comparison key for the prerelease component.

        ``(0, ())`` for an absent prerelease ranks above ``(-1, ...)`` for any
        present prerelease, matching semver §11.3 ("a version with a prerelease
        is less than the same version without").
        """
        if self.prerelease is None:
            return (0, ())
        segments = tuple(self._prerelease_segment_key(s) for s in self.prerelease.split("."))
        return (-1, segments)

    def _compare_key(self, other: "ParsedVersion"):
        """Build (self_key, other_key) for ordered comparison against ``other``."""
        length = max(len(self.release), len(other.release))
        return (
            (self._release_key(length), self._prerelease_key()),
            (other._release_key(length), other._prerelease_key()),
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ParsedVersion):
            return NotImplemented
        a, b = self._compare_key(other)
        return a == b

    def __lt__(self, other: "ParsedVersion") -> bool:
        if not isinstance(other, ParsedVersion):
            return NotImplemented
        a, b = self._compare_key(other)
        return a < b

    def __le__(self, other: "ParsedVersion") -> bool:
        if not isinstance(other, ParsedVersion):
            return NotImplemented
        a, b = self._compare_key(other)
        return a <= b

    def __gt__(self, other: "ParsedVersion") -> bool:
        if not isinstance(other, ParsedVersion):
            return NotImplemented
        a, b = self._compare_key(other)
        return a > b

    def __ge__(self, other: "ParsedVersion") -> bool:
        if not isinstance(other, ParsedVersion):
            return NotImplemented
        a, b = self._compare_key(other)
        return a >= b

    def __hash__(self) -> int:
        # Hash with trailing zeros stripped so 2026.4.0 and 2026.4.0.0 hash the same.
        stripped = self.release
        while len(stripped) > 1 and stripped[-1] == 0:
            stripped = stripped[:-1]
        return hash((stripped, self._prerelease_key()))


# Sentinel: sorts strictly below every parseable ParsedVersion. The parser only
# ever produces non-negative release components, so a release tuple containing
# -1 is unreachable from `parse()` and compares less than every real version
# under tuple ordering after zero-padding.
ParsedVersion.MIN = ParsedVersion(  # type: ignore[attr-defined]
    original="",
    release=(-1,),
    prerelease=None,
    build=None,
)


def version_sort_key(image_version: "ImageVersion") -> ParsedVersion:
    """Sort key for ``ImageVersion``: unparseable / matrix versions sort first.

    Use as: ``sorted(versions, key=version_sort_key)``. Parseable versions
    sort in ascending semver order; ``ImageVersion`` instances whose
    ``parsed_version`` is ``None`` (matrix versions or unparseable names)
    collapse to ``ParsedVersion.MIN`` and lead the sorted list.
    """
    parsed = image_version.parsed_version
    return parsed if parsed is not None else ParsedVersion.MIN
