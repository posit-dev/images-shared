import pytest
from _pytest.mark import ParameterSet
from pydantic import ValidationError

from posit_bakery.plugins.builtin.trivy.options import TrivyOptions, parse_severities, validate_timeout

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]


class TestTrivyOptions:
    def test_defaults(self):
        opts = TrivyOptions()
        assert opts.tool == "trivy"
        assert opts.severity is None
        assert opts.ignoreUnfixed is None
        assert opts.skipFiles is None
        assert opts.skipDirs is None
        assert opts.exitCode is None
        assert opts.scanners is None
        assert opts.timeout is None
        assert opts.failureSeverity is None

    def test_explicit_values(self):
        opts = TrivyOptions(
            severity=["CRITICAL", "HIGH"],
            ignoreUnfixed=True,
            skipFiles=["test.lock"],
            skipDirs=["/tmp"],
            exitCode=1,
            scanners=["vuln", "secret"],
            timeout="5m0s",
            failureSeverity=["CRITICAL"],
        )
        assert opts.severity == ["CRITICAL", "HIGH"]
        assert opts.ignoreUnfixed is True
        assert opts.skipFiles == ["test.lock"]
        assert opts.skipDirs == ["/tmp"]
        assert opts.exitCode == 1
        assert opts.scanners == ["vuln", "secret"]
        assert opts.timeout == "5m0s"
        assert opts.failureSeverity == ["CRITICAL"]

    def test_failure_severity_normalised(self):
        assert TrivyOptions(failureSeverity=[" high", "Critical "]).failureSeverity == ["HIGH", "CRITICAL"]

    @pytest.mark.parametrize("bad", [["HIGHH"], ["UNKNOWN"], [""], []])
    def test_failure_severity_rejects_bad_values(self, bad):
        with pytest.raises(ValidationError):
            TrivyOptions(failureSeverity=bad)

    @pytest.mark.parametrize("good", ["5m0s", "30s", "1h30m", "1.5h"])
    def test_timeout_accepts_go_durations(self, good):
        assert TrivyOptions(timeout=good).timeout == good

    @pytest.mark.parametrize("bad", ["soon", "5", "5 m", "5m,", ""])
    def test_timeout_rejects_non_durations(self, bad):
        with pytest.raises(ValidationError):
            TrivyOptions(timeout=bad)

    def test_helpers_raise_value_error(self):
        with pytest.raises(ValueError):
            parse_severities(["nope"])
        with pytest.raises(ValueError):
            validate_timeout("nope")

    @staticmethod
    def merge_params() -> list[ParameterSet]:
        return [
            pytest.param(
                {},
                {},
                {
                    "severity": None,
                    "ignoreUnfixed": None,
                    "skipFiles": None,
                    "skipDirs": None,
                    "exitCode": None,
                    "scanners": None,
                    "timeout": None,
                    "failureSeverity": None,
                },
                id="both_default",
            ),
            pytest.param(
                {},
                {"severity": ["HIGH"], "exitCode": 1},
                {
                    "severity": ["HIGH"],
                    "ignoreUnfixed": None,
                    "skipFiles": None,
                    "skipDirs": None,
                    "exitCode": 1,
                    "scanners": None,
                    "timeout": None,
                    "failureSeverity": None,
                },
                id="left_default_right_set",
            ),
            pytest.param(
                {"severity": ["CRITICAL"], "ignoreUnfixed": True},
                {},
                {
                    "severity": ["CRITICAL"],
                    "ignoreUnfixed": True,
                    "skipFiles": None,
                    "skipDirs": None,
                    "exitCode": None,
                    "scanners": None,
                    "timeout": None,
                    "failureSeverity": None,
                },
                id="left_set_right_default",
            ),
            pytest.param(
                {"severity": ["CRITICAL"], "skipFiles": ["a.lock"]},
                {"severity": ["HIGH"], "skipFiles": ["b.lock"], "exitCode": 2},
                {
                    "severity": ["CRITICAL"],
                    "ignoreUnfixed": None,
                    "skipFiles": ["a.lock"],
                    "skipDirs": None,
                    "exitCode": 2,
                    "scanners": None,
                    "timeout": None,
                    "failureSeverity": None,
                },
                id="left_wins_when_set",
            ),
            pytest.param(
                {"scanners": ["vuln"], "failureSeverity": ["CRITICAL"]},
                {"scanners": ["secret"], "timeout": "5m0s", "failureSeverity": ["HIGH"]},
                {
                    "severity": None,
                    "ignoreUnfixed": None,
                    "skipFiles": None,
                    "skipDirs": None,
                    "exitCode": None,
                    "scanners": ["vuln"],
                    "timeout": "5m0s",
                    "failureSeverity": ["CRITICAL"],
                },
                id="new_fields_merge_left_wins_right_fills_gaps",
            ),
        ]

    @pytest.mark.parametrize("left,right,expected", merge_params())
    def test_update(self, left, right, expected):
        left_options = TrivyOptions(**left)
        right_options = TrivyOptions(**right)
        merged = left_options.update(right_options)

        for key, value in expected.items():
            assert getattr(merged, key) == value, f"Expected {key} to be {value}, got {getattr(merged, key)}"
