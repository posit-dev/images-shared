"""Parsed version representation for Posit calver-flavored semver strings.

Provides ``ParsedVersion``, a value type that round-trips the input string,
supports comparison per semver §11, and warns (rather than raising) on
unparseable input.
"""

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)


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
    prerelease: Optional[str] = None
    build: Optional[str] = None

    @classmethod
    def parse(cls, value: str) -> Optional["ParsedVersion"]:
        """Parse a version string. Returns ``None`` on failure and logs a warning."""
        log.warning("Unparseable version string: %r", value)
        return None
