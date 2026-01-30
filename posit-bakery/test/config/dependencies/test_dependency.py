from pydantic import BaseModel
import pytest

from posit_bakery.config.dependencies import (
    DependencyConstraintField,
    DependencyVersionsField,
    DependencyVersions,
    get_dependency_versions_class,
    get_dependency_constraint_class,
)
from posit_bakery.config.dependencies.dependency import Dependency
from posit_bakery.config.dependencies.python import PythonDependencyVersions, PythonDependencyConstraint
from posit_bakery.config.dependencies.quarto import QuartoDependencyVersions, QuartoDependencyConstraint
from posit_bakery.config.dependencies.r import RDependencyVersions, RDependencyConstraint


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
            pytest.param("0.1.2", id="single_version_string"),
            pytest.param(["0.1.2"], id="single_version"),
            pytest.param(["1.0.0", "2.0.0"], id="multiple_versions"),
            pytest.param("0.1.2,2.0.0", id="multi_version_string"),
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
        if isinstance(versions, str):
            versions = [v.strip() for v in versions.split(",")]

        assert dep.dependency.versions == versions

    def test_version_alias(self):
        dep = FakeDependencyVersions(
            dependency={
                "dependency": "python",
                "version": "3.9.1",
            }
        )
        assert dep.dependency.versions == ["3.9.1"]

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

    @pytest.mark.parametrize(
        "versions_obj,expected_dict",
        [
            pytest.param(
                PythonDependencyVersions(dependency="python", versions=["3.8.10"]),
                {"dependency": "python", "version": "3.8.10"},
                id="python_single_version",
            ),
            pytest.param(
                PythonDependencyVersions(dependency="python", versions=["3.8.10", "3.9.5"]),
                {"dependency": "python", "versions": ["3.8.10", "3.9.5"]},
                id="python_multiple_versions",
            ),
            pytest.param(
                RDependencyVersions(dependency="R", versions=["4.0.5"]),
                {"dependency": "R", "version": "4.0.5"},
                id="R_single_version",
            ),
            pytest.param(
                RDependencyVersions(dependency="R", versions=["4.0.5", "4.1.2"]),
                {"dependency": "R", "versions": ["4.0.5", "4.1.2"]},
                id="R_multiple_versions",
            ),
            pytest.param(
                QuartoDependencyVersions(dependency="quarto", versions=["1.7.34"]),
                {"dependency": "quarto", "version": "1.7.34"},
                id="quarto_single_version",
            ),
            pytest.param(
                QuartoDependencyVersions(dependency="quarto", versions=["1.7.34", "1.6.43"]),
                {"dependency": "quarto", "versions": ["1.7.34", "1.6.43"]},
                id="quarto_multiple_versions",
            ),
        ],
    )
    def test_version_serialization(self, versions_obj: DependencyVersions, expected_dict: dict):
        """Test that version serialization works as expected."""
        serialized = versions_obj.model_dump(exclude_unset=True, exclude_defaults=True, exclude_none=True)
        assert serialized == expected_dict


class TestGetDependencyVersionsClass:
    """Tests for the get_dependency_versions_class helper function."""

    @pytest.mark.parametrize(
        "dependency_name,expected_class",
        [
            pytest.param("python", PythonDependencyVersions, id="python"),
            pytest.param("R", RDependencyVersions, id="R"),
            pytest.param("quarto", QuartoDependencyVersions, id="quarto"),
        ],
    )
    def test_valid_dependency_names(self, dependency_name: str, expected_class: type):
        """Test that valid dependency names return the correct class."""
        result = get_dependency_versions_class(dependency_name)
        assert result is expected_class

    @pytest.mark.parametrize(
        "invalid_name",
        [
            pytest.param("Python", id="wrong_case_python"),
            pytest.param("r", id="wrong_case_r"),
            pytest.param("Quarto", id="wrong_case_quarto"),
            pytest.param("node", id="unsupported_node"),
            pytest.param("rust", id="unsupported_rust"),
            pytest.param("", id="empty_string"),
            pytest.param("invalid", id="invalid_name"),
        ],
    )
    def test_invalid_dependency_name_raises(self, invalid_name: str):
        """Test that invalid dependency names raise ValueError."""
        with pytest.raises(ValueError, match=f"Unsupported dependency name: {invalid_name}"):
            get_dependency_versions_class(invalid_name)


class TestGetDependencyConstraintClass:
    """Tests for the get_dependency_constraint_class helper function."""

    @pytest.mark.parametrize(
        "dependency_name,expected_class",
        [
            pytest.param("python", PythonDependencyConstraint, id="python"),
            pytest.param("R", RDependencyConstraint, id="R"),
            pytest.param("quarto", QuartoDependencyConstraint, id="quarto"),
        ],
    )
    def test_valid_dependency_names(self, dependency_name: str, expected_class: type):
        """Test that valid dependency names return the correct class."""
        result = get_dependency_constraint_class(dependency_name)
        assert result is expected_class

    @pytest.mark.parametrize(
        "invalid_name",
        [
            pytest.param("Python", id="wrong_case_python"),
            pytest.param("r", id="wrong_case_r"),
            pytest.param("Quarto", id="wrong_case_quarto"),
            pytest.param("java", id="unsupported_java"),
            pytest.param("go", id="unsupported_go"),
            pytest.param("", id="empty_string"),
            pytest.param("unknown", id="unknown_name"),
        ],
    )
    def test_invalid_dependency_name_raises(self, invalid_name: str):
        """Test that invalid dependency names raise ValueError."""
        with pytest.raises(ValueError, match=f"Unsupported dependency name: {invalid_name}"):
            get_dependency_constraint_class(invalid_name)
