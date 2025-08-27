from unittest.mock import MagicMock, patch

from pydantic import BaseModel
import pytest

from posit_bakery.config.dependencies import (
    Dependency,
    DependencyField,
    DependencyVersion,
    RDependency,
    PythonDependency,
    QuartoDependency,
    VersionConstraint,
)
from test.config.dependencies.test_version import R_VERSIONS, PYTHON_VERSIONS


pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.dependency,
]


class FakeDependency(BaseModel):
    """A fake model to test the DependencyField discriminator."""

    dependency: DependencyField

    def available_versions(self) -> list[DependencyVersion]:
        return []


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
        dep = FakeDependency(
            dependency={
                "dependency": "R",
                "versions": versions,
            }
        )

        assert dep.dependency.versions == versions

    def test_version_list_empty(self):
        """Test that empty list fails validation.."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FakeDependency(
                dependency={
                    "dependency": "python",
                    "versions": [],
                }
            )

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
            FakeDependency(
                dependency={
                    "dependency": "quarto",
                    "versions": versions,
                }
            )

    @pytest.mark.parametrize(
        "discriminator,expected_type",
        [
            pytest.param("python", PythonDependency, id="python"),
            pytest.param("R", RDependency, id="R"),
            pytest.param("quarto", QuartoDependency, id="quarto"),
        ],
    )
    def test_dependency_discriminator(self, discriminator: str, expected_type: type[Dependency]):
        """Test that the discriminator field correctly identifies the dependency type."""
        dep = FakeDependency(
            dependency={
                "dependency": discriminator,
                "versions": ["1.0.0"],
            }
        )

        assert isinstance(dep.dependency, expected_type)
        assert dep.dependency.dependency == discriminator
