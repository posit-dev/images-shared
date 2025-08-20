import pytest


pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.dependency,
]

from posit_bakery.config.dependencies import VersionConstraint


class TestVersionConstraint:
    @pytest.mark.parametrize(
        "count,latest",
        [
            pytest.param(None, True, id="latest_only"),
            pytest.param(1, None, id="count_only"),
        ],
    )
    def test_version_constraint_latest_valid(self, count, latest):
        """Test that a version constraint with latest set to True is accepted."""
        ver = VersionConstraint(count=count, latest=latest)

        assert ver.count == count
        assert ver.latest == latest

    @pytest.mark.parametrize(
        "count,latest",
        [
            pytest.param(0, None, id="count_zero"),
            pytest.param(-15, None, id="count_negative"),
            pytest.param(None, 67, id="latest_int"),
            pytest.param(None, 3.14, id="latest_float"),
        ],
    )
    def test_version_constraint_latest_invalid(self, count, latest):
        """Test that a version constraint with latest set to True is accepted."""
        with pytest.raises(ValueError):
            VersionConstraint(count=count, latest=latest)

    @pytest.mark.parametrize(
        "count,latest,max,min",
        [
            pytest.param(None, True, "2.0.0", None, id="latest_max"),
            pytest.param(None, True, None, "1.0.0", id="latest_min"),
            pytest.param(5, None, "3.0.0", "2.0.0", id="count_max_min"),
        ],
    )
    def test_version_constraint_mutually_exclusive(self, count, latest, max, min):
        """Test that a version constraint with latest, max, and min is mutually exclusive."""
        with pytest.raises(ValueError):
            VersionConstraint(count=count, latest=latest, max=max, min=min)
