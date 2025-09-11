from typing import Literal
from unittest.mock import MagicMock, patch

from pydantic import BaseModel
import pytest

from posit_bakery.config.dependencies import DependencyConstraintField, DependencyVersionsField
from posit_bakery.config.dependencies.dependency import Dependency, DependencyConstraint, DependencyVersions
from posit_bakery.config.dependencies.python import PythonDependencyConstraint, PythonDependencyVersions
from posit_bakery.config.dependencies.quarto import QuartoDependencyConstraint, QuartoDependencyVersions
from posit_bakery.config.dependencies.r import RDependencyConstraint, RDependencyVersions


from test.config.dependencies.test_version import R_VERSIONS, PYTHON_VERSIONS


pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
    pytest.mark.dependency,
]


class TestDependency:
    def test_init_error(self):
        """Test that instantiating the base class raises an error."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            Dependency()


class FakeDependencyConstraint(BaseModel):
    """A fake model to test the DependencyConstraintField discriminator."""

    dependency: DependencyConstraintField

    def available_versions(self) -> list:
        return []


class FakeDependencyVersions(BaseModel):
    """A fake model to test the DependencyVersionsField discriminator."""

    dependency: DependencyVersionsField

    def available_versions(self) -> list:
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
        dep = FakeDependencyVersions(
            dependency={
                "dependency": "R",
                "versions": versions,
            }
        )

        assert dep.dependency.versions == versions

    def test_version_list_empty(self):
        """Test that empty list fails validation.."""
        with pytest.raises(ValueError, match="cannot be empty"):
            FakeDependencyVersions(
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
            FakeDependencyVersions(
                dependency={
                    "dependency": "quarto",
                    "versions": versions,
                }
            )

    @pytest.mark.parametrize(
        "discriminator,expected_type",
        [
            pytest.param("python", PythonDependencyVersions, id="python"),
            pytest.param("R", RDependencyVersions, id="R"),
            pytest.param("quarto", QuartoDependencyVersions, id="quarto"),
        ],
    )
    def test_dependency_discriminator(self, discriminator: str, expected_type: type[DependencyVersions]):
        """Test that the discriminator field correctly identifies the dependency type."""
        dep = FakeDependencyVersions(
            dependency={
                "dependency": discriminator,
                "versions": ["1.0.0"],
            }
        )

        assert isinstance(dep.dependency, expected_type)
        assert dep.dependency.dependency == discriminator
