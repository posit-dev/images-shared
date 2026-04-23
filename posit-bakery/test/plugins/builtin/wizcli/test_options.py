import pytest
from _pytest.mark import ParameterSet

from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions

pytestmark = [
    pytest.mark.unit,
    pytest.mark.wizcli,
]


class TestWizCLIOptions:
    def test_defaults(self):
        opts = WizCLIOptions()
        assert opts.tool == "wizcli"
        assert opts.projects is None
        assert opts.policies is None
        assert opts.tags is None
        assert opts.scanOsManagedLibraries is None
        assert opts.scanGoStandardLibrary is None

    def test_explicit_values(self):
        opts = WizCLIOptions(
            projects=["proj-1"],
            policies=["pol-1"],
            tags=["team=platform"],
            scanOsManagedLibraries=True,
            scanGoStandardLibrary=False,
        )
        assert opts.projects == ["proj-1"]
        assert opts.policies == ["pol-1"]
        assert opts.tags == ["team=platform"]
        assert opts.scanOsManagedLibraries is True
        assert opts.scanGoStandardLibrary is False

    @staticmethod
    def merge_params() -> list[ParameterSet]:
        return [
            pytest.param({}, {}, {
                "projects": None, "policies": None, "tags": None,
                "scanOsManagedLibraries": None, "scanGoStandardLibrary": None,
            }, id="both_default"),
            pytest.param({}, {"projects": ["p1"], "policies": ["pol1"]}, {
                "projects": ["p1"], "policies": ["pol1"], "tags": None,
                "scanOsManagedLibraries": None, "scanGoStandardLibrary": None,
            }, id="left_default_right_set"),
            pytest.param({"projects": ["p2"], "scanOsManagedLibraries": True}, {}, {
                "projects": ["p2"], "policies": None, "tags": None,
                "scanOsManagedLibraries": True, "scanGoStandardLibrary": None,
            }, id="left_set_right_default"),
            pytest.param(
                {"projects": ["p2"], "tags": ["env=ci"]},
                {"projects": ["p1"], "tags": ["env=prod"], "scanGoStandardLibrary": True},
                {"projects": ["p2"], "policies": None, "tags": ["env=ci"],
                 "scanOsManagedLibraries": None, "scanGoStandardLibrary": True},
                id="left_wins_when_set",
            ),
        ]

    @pytest.mark.parametrize("left,right,expected", merge_params())
    def test_update(self, left, right, expected):
        left_options = WizCLIOptions(**left)
        right_options = WizCLIOptions(**right)
        merged = left_options.update(right_options)

        for key, value in expected.items():
            assert getattr(merged, key) == value, (
                f"Expected {key} to be {value}, got {getattr(merged, key)}"
            )
