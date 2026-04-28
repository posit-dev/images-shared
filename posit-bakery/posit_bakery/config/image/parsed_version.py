"""Parsed version representation for Posit calver-flavored semver strings.

Provides ``ParsedVersion``, a value type that round-trips the input string,
supports comparison per semver §11, and warns (rather than raising) on
unparseable input.
"""

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)

# Anchored grammar:
#   <release>      one or more dot-separated digit groups, minimum two groups
#   -<prerelease>  optional, semver prerelease alphabet
#   +<build>       optional, semver build alphabet
_VERSION_RE = re.compile(
    r"^(?P<release>\d+(?:\.\d+){1,})"
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
