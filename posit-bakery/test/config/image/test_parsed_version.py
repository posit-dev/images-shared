import logging
from unittest.mock import MagicMock

import pytest

from posit_bakery.config.image.parsed_version import ParsedVersion
from posit_bakery.config.image.parsed_version import version_sort_key

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


def _p(s: str) -> ParsedVersion:
    """Helper: parse a known-good string and assert success."""
    parsed = ParsedVersion.parse(s)
    assert parsed is not None, f"failed to parse {s!r}"
    return parsed


class TestComparison:
    @pytest.mark.parametrize(
        "ascending",
        [
            # Each list is in strictly ascending order.
            ["2026.04.0", "2026.04.1"],  # patch increment
            ["2026.04.1", "2026.05.0"],  # minor increment
            ["2026.04.9", "2026.04.10"],  # rollover (the bug from #499)
            ["2026.04.0-daily", "2026.04.0-dev", "2026.04.0"],  # lexicographic prerelease order; presence < absence
            ["2026.04.0-1", "2026.04.0-alpha"],  # numeric < alphanumeric segment
            ["2026.03.1", "2026.04.0-daily", "2026.04.0", "2026.04.1"],
        ],
    )
    def test_ordered_chain(self, ascending):
        parsed = [_p(s) for s in ascending]
        for i in range(len(parsed)):
            for j in range(i + 1, len(parsed)):
                a, b = parsed[i], parsed[j]
                assert a < b, f"expected {a} < {b}"
                assert b > a
                assert a <= b
                assert b >= a
                assert a != b

    @pytest.mark.parametrize(
        "a,b",
        [
            # Zero-padding equivalence.
            ("2026.4.0", "2026.04.0"),
            # Trailing-zero release-tuple equivalence.
            ("2026.4.0", "2026.4.0.0"),
            # Build metadata ignored for comparison.
            ("2026.04.0+a", "2026.04.0+b"),
            # Mixed: zero-padding + build difference.
            ("2026.4.0+x", "2026.04.0+y"),
        ],
    )
    def test_equality(self, a, b):
        pa, pb = _p(a), _p(b)
        assert pa == pb
        assert not (pa < pb)
        assert not (pa > pb)
        assert pa <= pb
        assert pa >= pb
        assert hash(pa) == hash(pb)

    def test_set_dedup_uses_comparison_equality(self):
        """ParsedVersions equal under spec rules collapse in a set."""
        items = {_p("2026.4.0"), _p("2026.04.0"), _p("2026.04.0+x")}
        assert len(items) == 1

    def test_str_preserves_original_after_equality(self):
        """Equality does not erase the original string."""
        a = _p("2026.4.0+x")
        b = _p("2026.04.0+y")
        assert a == b
        assert str(a) == "2026.4.0+x"
        assert str(b) == "2026.04.0+y"


class TestMinSentinel:
    @pytest.mark.parametrize(
        "value",
        ["2026.04.0", "2026.04.0-daily", "1.0.0", "2025.12.0-14"],
    )
    def test_min_less_than_any_parseable(self, value):
        parsed = _p(value)
        assert ParsedVersion.MIN < parsed
        assert parsed > ParsedVersion.MIN
        assert ParsedVersion.MIN != parsed

    def test_min_equal_to_self(self):
        assert ParsedVersion.MIN == ParsedVersion.MIN
        assert hash(ParsedVersion.MIN) == hash(ParsedVersion.MIN)

    def test_min_str_is_empty(self):
        assert str(ParsedVersion.MIN) == ""


class TestVersionSortKey:
    def test_sorts_with_unparseable_first(self):
        """Mixed list sorts: matrix/garbage first (via MIN), then ascending parseable."""

        # Build mock ImageVersions with the three relevant fields.
        def mock_iv(name: str, *, is_matrix: bool = False) -> MagicMock:
            iv = MagicMock()
            iv.name = name
            iv.isMatrixVersion = is_matrix
            iv.parsed_version = None if is_matrix else ParsedVersion.parse(name)
            return iv

        items = [
            mock_iv("2026.04.1"),
            mock_iv("R4.3.3-python3.11.15", is_matrix=True),
            mock_iv("2026.04.0"),
            mock_iv("garbage"),  # unparseable, parsed_version is None
            mock_iv("2026.05.0-dev+62-g1ca9367735"),
        ]
        ordered = sorted(items, key=version_sort_key)
        names = [iv.name for iv in ordered]
        # Two unparseable/matrix entries lead, in original relative order
        # (Python's sort is stable). Parseable entries follow in ascending order.
        assert names[:2] == ["R4.3.3-python3.11.15", "garbage"]
        assert names[2:] == ["2026.04.0", "2026.04.1", "2026.05.0-dev+62-g1ca9367735"]
