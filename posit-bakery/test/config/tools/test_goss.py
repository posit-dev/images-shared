import pytest
from _pytest.mark import ParameterSet

from posit_bakery.config.tools import GossOptions


class TestGoss:
    @staticmethod
    def merge_params() -> list[ParameterSet]:
        return [
            pytest.param({}, {}, {"command": "sleep infinity", "wait": 0}, id="default"),
            pytest.param({}, {"command": "command", "wait": 5}, {"command": "command", "wait": 5}, id="left_default"),
            pytest.param({"command": "command", "wait": 5}, {}, {"command": "command", "wait": 5}, id="right_default"),
            pytest.param(
                {"command": "command", "wait": 5},
                {"command": "other_command", "wait": 10},
                {"command": "command", "wait": 5},
                id="both_custom",
            ),
            pytest.param(
                {"command": "sleep infinity", "wait": 0},
                {"command": "other_command", "wait": 10},
                {"command": "sleep infinity", "wait": 0},
                id="left_set_defaults",
            ),
        ]

    @pytest.mark.parametrize("left,right,expected", merge_params())
    def test_merge(self, left, right, expected):
        left_options = GossOptions(**left)
        right_options = GossOptions(**right)
        merged = left_options.merge(right_options)

        for key, value in expected.items():
            assert getattr(merged, key) == value, f"Expected {key} to be {value}, got {getattr(merged, key)}"
