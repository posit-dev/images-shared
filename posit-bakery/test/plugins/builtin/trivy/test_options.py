import pytest
from _pytest.mark import ParameterSet

from posit_bakery.plugins.builtin.trivy.options import TrivyOptions

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]


class TestTrivyOptions:
    def test_defaults(self):
        opts = TrivyOptions()
        assert opts.tool == "trivy"
        assert opts.severity is None
        assert opts.failOnSeverity is None
        assert opts.disabledScanners is None
        assert opts.timeout is None

    def test_explicit_values(self):
        opts = TrivyOptions(
            severity=["HIGH", "CRITICAL"],
            failOnSeverity=["CRITICAL"],
            disabledScanners=["secret"],
            timeout="10m",
        )
        assert opts.severity == ["HIGH", "CRITICAL"]
        assert opts.failOnSeverity == ["CRITICAL"]
        assert opts.disabledScanners == ["secret"]
        assert opts.timeout == "10m"

    @staticmethod
    def merge_params() -> list[ParameterSet]:
        return [
            pytest.param(
                {},
                {},
                {"severity": None, "failOnSeverity": None, "disabledScanners": None, "timeout": None},
                id="both_default",
            ),
            pytest.param(
                {},
                {"severity": ["HIGH"], "timeout": "5m"},
                {"severity": ["HIGH"], "failOnSeverity": None, "disabledScanners": None, "timeout": "5m"},
                id="left_default_right_set",
            ),
            pytest.param(
                {"severity": ["CRITICAL"], "disabledScanners": ["secret"]},
                {},
                {"severity": ["CRITICAL"], "failOnSeverity": None, "disabledScanners": ["secret"], "timeout": None},
                id="left_set_right_default",
            ),
            pytest.param(
                {"severity": ["HIGH"], "timeout": "5m"},
                {"severity": ["CRITICAL"], "timeout": "10m", "failOnSeverity": ["CRITICAL"]},
                {"severity": ["HIGH"], "failOnSeverity": ["CRITICAL"], "disabledScanners": None, "timeout": "5m"},
                id="left_wins_when_set",
            ),
        ]

    @pytest.mark.parametrize("left,right,expected", merge_params())
    def test_update(self, left, right, expected):
        left_options = TrivyOptions(**left)
        right_options = TrivyOptions(**right)
        merged = left_options.update(right_options)

        for key, value in expected.items():
            assert getattr(merged, key) == value, f"Expected {key} to be {value}, got {getattr(merged, key)}"
