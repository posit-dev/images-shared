import pytest


pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.dependency,
]

from posit_bakery.config.dependencies import Dependency


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
            pytest.param([1], id="list_ints"),
            pytest.param([1.0, 2.0], id="list_floats"),
            pytest.param(["1.0.0", 2], id="list_mixed"),
        ],
    )
    def test_version_list_invalid_type(self, versions):
        """Test that invalid types for version list fail validation."""
        with pytest.raises(ValueError):
            Dependency(versions=versions)
