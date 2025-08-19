import pytest


pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]

from posit_bakery.config.dependencies import Dependency, VersionsConstraint


class TestDependencyVersions:
    @pytest.mark.parametrize(
        "versions",
        [
            pytest.param(["0.1.2"], id="single_version"),
            pytest.param(["1.0.0", "2.0.0"], id="multiple_versions"),
            pytest.param(["1.0.0", "2.0.0", "3.0.0"], id="three_versions"),
        ],
    )
    def test_version_list_valid(self, versions):
        """Test that a valid version list is accepted."""
        dep = Dependency(versions=versions)

        assert dep.versions == versions

    def test_version_list_empty(self):
        """Test that empty list fails validation.."""
        with pytest.raises(ValueError, match="cannot be empty"):
            Dependency(versions=[])

    @pytest.mark.parametrize(
        "versions",
        [
            pytest.param("1.0.0", id="string"),
            pytest.param(1.5, id="float"),
            pytest.param(123, id="integer"),
            pytest.param(None, id="none"),
            pytest.param({"version": "1.0.0"}, id="dict"),
            pytest.param([1], id="list_ints"),
            pytest.param([1.0, 2.0], id="list_floats"),
            pytest.param(["1.0.0", 2], id="list_mixed"),
        ],
    )
    def test_version_list_invalid_type(self, versions):
        """Test that invalid types for version list fail validation."""
        with pytest.raises(ValueError):
            Dependency(versions=versions)

    @pytest.mark.parametrize(
        "constraint",
        [
            pytest.param(VersionsConstraint(count=None, latest=True), id="latest_only"),
            pytest.param(VersionsConstraint(count=1, latest=None), id="count_only"),
        ],
    )
    def test_version_constraint_latest_valid(self, constraint):
        """Test that a version constraint with latest set to True is accepted."""
        dep = Dependency(versions=constraint)

        assert dep.versions == constraint

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
            VersionsConstraint(count=count, latest=latest)
