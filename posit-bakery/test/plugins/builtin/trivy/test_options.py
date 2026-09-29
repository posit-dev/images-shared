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
        assert opts.ignoreUnfixed is None
        assert opts.skipFiles is None
        assert opts.skipDirs is None
        assert opts.exitCode is None

    def test_explicit_values(self):
        opts = TrivyOptions(
            severity=["CRITICAL", "HIGH"],
            ignoreUnfixed=True,
            skipFiles=["test.lock"],
            skipDirs=["/tmp"],
            exitCode=1,
        )
        assert opts.severity == ["CRITICAL", "HIGH"]
        assert opts.ignoreUnfixed is True
        assert opts.skipFiles == ["test.lock"]
        assert opts.skipDirs == ["/tmp"]
        assert opts.exitCode == 1

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
                },
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
