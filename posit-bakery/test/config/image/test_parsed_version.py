import logging

import pytest

from posit_bakery.config.image.parsed_version import ParsedVersion

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestParseUnparseable:
    @pytest.mark.parametrize(
        "value",
        [
            "",
            "latest",
            "R4.3.3-python3.11.15",
            "v1.2.3",
            "not a version",
            "1",  # only one release component
        ],
    )
    def test_returns_none(self, value, caplog):
        """Unparseable inputs return None and emit exactly one log.warning."""
        caplog.set_level(logging.WARNING)
        result = ParsedVersion.parse(value)
        assert result is None
        warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
        assert len(warnings) == 1
        assert "Unparseable version string" in warnings[0].message
        assert repr(value) in warnings[0].message


class TestParseRoundtrip:
    @pytest.mark.parametrize(
        "value,release,prerelease,build",
        [
            # The six exemplars from issue #499.
            ("2026.04.0+526.pro2", (2026, 4, 0), None, "526.pro2"),
            ("2026.05.0-daily+92", (2026, 5, 0), "daily", "92"),
            ("2026.03.1", (2026, 3, 1), None, None),
            ("2026.04.0-dev+485-gdb8245deea", (2026, 4, 0), "dev", "485-gdb8245deea"),
            ("2026.04.1", (2026, 4, 1), None, None),
            ("2026.05.0-dev+62-g1ca9367735", (2026, 5, 0), "dev", "62-g1ca9367735"),
            # Older Package Manager stable: -N is build metadata, but parses as
            # a prerelease segment under the regex. Round-trips losslessly.
            ("2025.12.0-14", (2025, 12, 0), "14", None),
            # Edge: 2-component release.
            ("2026.4", (2026, 4), None, None),
            # Edge: 4-component release.
            ("2026.4.0.1", (2026, 4, 0, 1), None, None),
            # Edge: leading zeros preserved in original; parsed numerically.
            ("2026.04.01", (2026, 4, 1), None, None),
            # Edge: prerelease only.
            ("2026.4.0-rc.1", (2026, 4, 0), "rc.1", None),
            # Edge: build only.
            ("2026.4.0+abc", (2026, 4, 0), None, "abc"),
        ],
    )
    def test_parses_and_roundtrips(self, value, release, prerelease, build, caplog):
        """All valid inputs parse correctly, decompose as expected, and ``str()`` round-trips."""
        caplog.set_level(logging.WARNING)
        parsed = ParsedVersion.parse(value)
        assert parsed is not None
        assert parsed.original == value
        assert parsed.release == release
        assert parsed.prerelease == prerelease
        assert parsed.build == build
        assert str(parsed) == value
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
