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
