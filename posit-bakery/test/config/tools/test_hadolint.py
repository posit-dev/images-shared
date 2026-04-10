import pytest
from _pytest.mark import ParameterSet

from posit_bakery.plugins.builtin.hadolint.options import HadolintOptions

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hadolint,
]


class TestHadolintOptions:
    def test_defaults(self):
        """Test that HadolintOptions has correct defaults."""
        options = HadolintOptions()
        assert options.tool == "hadolint"
        assert options.failureThreshold is None
        assert options.ignored is None
        assert options.labelSchema is None
        assert options.noFail is None
        assert options.override is None
        assert options.strictLabels is None
        assert options.disableIgnorePragma is None
        assert options.trustedRegistries is None

    def test_with_all_fields(self):
        """Test creating HadolintOptions with all fields set."""
        options = HadolintOptions(
            failureThreshold="warning",
            ignored=["DL3008", "DL3009"],
            labelSchema={"maintainer": "text", "version": "semver"},
            noFail=True,
            override={"error": ["DL3001"], "warning": ["DL3002"]},
            strictLabels=True,
            disableIgnorePragma=True,
            trustedRegistries=["docker.io", "ghcr.io"],
        )
        assert options.failureThreshold == "warning"
        assert options.ignored == ["DL3008", "DL3009"]
        assert options.labelSchema == {"maintainer": "text", "version": "semver"}
        assert options.noFail is True
        assert options.override.error == ["DL3001"]
        assert options.override.warning == ["DL3002"]
        assert options.strictLabels is True
        assert options.disableIgnorePragma is True
        assert options.trustedRegistries == ["docker.io", "ghcr.io"]

    @staticmethod
    def merge_params() -> list[ParameterSet]:
        return [
            pytest.param({}, {}, {}, id="both_default"),
            pytest.param(
                {},
                {"failureThreshold": "warning", "ignored": ["DL3008"]},
                {"failureThreshold": "warning", "ignored": ["DL3008"]},
                id="left_default_right_set",
            ),
            pytest.param(
                {"failureThreshold": "error", "ignored": ["DL3009"]},
                {},
                {"failureThreshold": "error", "ignored": ["DL3009"]},
                id="left_set_right_default",
            ),
            pytest.param(
                {"failureThreshold": "error"},
                {"failureThreshold": "warning"},
                {"failureThreshold": "error"},
                id="both_set_left_wins",
            ),
            pytest.param(
                {"noFail": True},
                {"noFail": False, "strictLabels": True},
                {"noFail": True, "strictLabels": True},
                id="partial_overlap",
            ),
        ]

    @pytest.mark.parametrize("left,right,expected", merge_params())
    def test_update(self, left, right, expected):
        left_options = HadolintOptions(**left)
        right_options = HadolintOptions(**right)
        merged = left_options.update(right_options)

        for key, value in expected.items():
            assert getattr(merged, key) == value, f"Expected {key} to be {value}, got {getattr(merged, key)}"
