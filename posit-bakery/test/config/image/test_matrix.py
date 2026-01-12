from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from posit_bakery.config import Image
from posit_bakery.config.dependencies import PythonDependencyVersions, RDependencyVersions, QuartoDependencyVersions
from posit_bakery.config.image.matrix import generate_default_name_pattern, ImageMatrix


@pytest.mark.parametrize(
    "data,expected",
    [
        pytest.param(
            {},
            ValueError,
            id="no-parameters",
        ),
        pytest.param(
            {
                "dependencies": [
                    PythonDependencyVersions(
                        dependency="python",
                        versions=["3.8", "3.9", "3.10"],
                    ),
                ],
            },
            "{{ Dependencies.python }}",
            id="one-dependency",
        ),
        pytest.param(
            {
                "dependencies": [
                    PythonDependencyVersions(
                        dependency="python",
                        versions=["3.8", "3.9", "3.10"],
                    ),
                    RDependencyVersions(
                        dependency="R",
                        versions=["4.0", "4.1"],
                    ),
                    QuartoDependencyVersions(
                        dependency="quarto",
                        versions=["1.2", "1.3"],
                    ),
                ],
            },
            "{{ Dependencies.python }}-{{ Dependencies.R }}-{{ Dependencies.quarto }}",
            id="multiple-dependencies",
        ),
        pytest.param(
            {
                "values": {"go_version": ["1.24", "1.25"]},
            },
            "{{ Values.go_version }}",
            id="one-value",
        ),
        pytest.param(
            {
                "values": {"go_version": ["1.24", "1.25"], "pro_drivers_version": "2025.07.0"},
            },
            "{{ Values.go_version }}-{{ Values.pro_drivers_version }}",
            id="multiple-values",
        ),
        pytest.param(
            {
                "dependencies": [
                    PythonDependencyVersions(
                        dependency="python",
                        versions=["3.8", "3.9", "3.10"],
                    ),
                    RDependencyVersions(
                        dependency="R",
                        versions=["4.0", "4.1"],
                    ),
                ],
                "values": {"go_version": ["1.24", "1.25"]},
            },
            "{{ Dependencies.python }}-{{ Dependencies.R }}-{{ Values.go_version }}",
            id="dependencies-and-values",
        ),
    ],
)
def test_generate_default_name_pattern(data, expected):
    if expected is ValueError:
        with pytest.raises(expected):
            generate_default_name_pattern(data)
    else:
        pattern = generate_default_name_pattern(data)
        assert pattern == expected


class TestImageMatrix:
    def test_dependencies_or_values_required(self, caplog):
        """Test that an ImageMatrix object requires a name."""
        with pytest.raises(
            ValidationError, match="At least one of 'dependencies' or 'values' must be defined for an image matrix"
        ):
            ImageMatrix(namePattern="test")
        assert "WARNING" not in caplog.text

    def test_valid(self):
        """Test that a valid ImageMatrix object can be created."""
        matrix = ImageMatrix(
            dependencies=[
                PythonDependencyVersions(
                    dependency="python",
                    versions=["3.8", "3.9"],
                ),
            ],
            values={
                "go_version": ["1.24", "1.25"],
            },
        )
        assert matrix.namePattern == "{{ Dependencies.python }}-{{ Values.go_version }}"
        assert matrix.subpath == "matrix"
        assert len(matrix.dependencies) == 1
        assert matrix.dependencies[0].dependency == "python"
        assert matrix.dependencies[0].versions == ["3.8", "3.9"]
        assert matrix.values == {"go_version": ["1.24", "1.25"]}

    def test_deduplicate_registries(self, caplog):
        """Test that duplicate registries are deduplicated."""
        ImageMatrix(
            values={"go_version": ["1.24", "1.25"]},
            extraRegistries=[
                {"host": "registry1.example.com", "namespace": "namespace1"},
                {"host": "registry1.example.com", "namespace": "namespace1"},  # Duplicate
            ],
        )
        assert "WARNING" in caplog.text
        assert (
            "Duplicate registry defined in config for image matrix with name pattern '{{ Values.go_version }}': "
            "registry1.example.com/namespace1" in caplog.text
        )

    def test_check_os_not_empty(self, caplog):
        """Test that an ImageMatrix must have at least one OS defined."""
        ImageMatrix(values={"go_version": ["1.24", "1.25"]}, os=[])
        assert "WARNING" in caplog.text
        assert (
            "No OSes defined for image matrix with name pattern '{{ Values.go_version }}'. At least one OS should be "
            "defined for complete tagging and labeling of images." in caplog.text
        )

    def test_deduplicate_os(self, caplog):
        """Test that duplicate OSes are deduplicated."""
        mock_parent = MagicMock(spec=Image)
        mock_parent.path = Path("/tmp/path")
        matrix = ImageMatrix(
            parent=mock_parent,
            values={"go_version": ["1.24", "1.25"]},
            os=[
                {"name": "Ubuntu 22.04", "primary": True},
                {"name": "Ubuntu 22.04"},  # Duplicate
            ],
        )
        assert len(matrix.os) == 1
        assert matrix.os[0].name == "Ubuntu 22.04"
        assert "WARNING" in caplog.text
        assert (
            "Duplicate OS defined in config for image matrix with name pattern '{{ Values.go_version }}': Ubuntu 22.04"
        ) in caplog.text

    def test_make_single_os_primary(self, caplog):
        """Test that if only one OS is defined, it is automatically made primary."""
        matrix = ImageMatrix(values={"go_version": ["1.24", "1.25"]}, os=[{"name": "Ubuntu 22.04"}])
        assert len(matrix.os) == 1
        assert matrix.os[0].primary is True
        assert matrix.os[0].name == "Ubuntu 22.04"
        assert "WARNING" not in caplog.text

    def test_max_one_primary_os(self):
        """Test that an error is raised if multiple primary OSes are defined."""
        with pytest.raises(
            ValidationError,
            match="Only one OS can be marked as primary for image matrix with name pattern '{{ Values.go_version }}'. Found 2 OSes marked primary.",
        ):
            ImageMatrix(
                values={"go_version": ["1.24", "1.25"]},
                os=[
                    {"name": "Ubuntu 22.04", "primary": True},
                    {"name": "Ubuntu 24.04", "primary": True},  # Multiple primary OSes
                ],
            )

    def test_no_primary_os_warning(self, caplog):
        """Test that a warning is logged if no primary OS is defined."""
        ImageMatrix(values={"go_version": ["1.24", "1.25"]}, os=[{"name": "Ubuntu 22.04"}, {"name": "Ubuntu 24.04"}])
        assert "WARNING" in caplog.text
        assert (
            "No OS marked as primary for image matrix with name pattern '{{ Values.go_version }}'. At least one OS should be marked as primary for "
            "complete tagging and labeling of images." in caplog.text
        )

    def test_check_duplicate_dependencies(self):
        """Test an error is raised if duplicate dependencies are defined."""
        with pytest.raises(
            ValidationError,
            match="Duplicate dependency or dependency constraints found in image matrix",
        ):
            ImageMatrix(
                values={"go_version": ["1.24", "1.25"]},
                dependencies=[
                    {"dependency": "R", "versions": ["4.2.3", "4.3.3"]},
                    {"dependency": "R", "versions": ["4.3.0"]},  # Duplicate dependency
                ],
            )

    def test_extra_registries_or_override_registries(self):
        """Test that only one of extraRegistries or overrideRegistries can be defined."""
        with pytest.raises(
            ValidationError,
            match="Only one of 'extraRegistries' or 'overrideRegistries' can be defined for image matrix with name pattern '{{ Values.go_version }}'.",
        ):
            ImageMatrix(
                values={"go_version": ["1.24", "1.25"]},
                extraRegistries=[{"host": "registry.example.com", "namespace": "namespace"}],
                overrideRegistries=[{"host": "another.registry.com", "namespace": "another_namespace"}],
            )

    def test_path_resolution(self):
        """Test that the path property resolves correctly based on the parent image's path and subpath."""
        mock_parent = MagicMock(spec=Image)
        mock_parent.path = Path("/tmp/path")
        matrix = ImageMatrix(
            values={"go_version": ["1.24", "1.25"]},
            parent=mock_parent,
        )
        assert matrix.path == Path("/tmp/path/matrix")

        matrix.subpath = "1.0"
        assert matrix.path == Path("/tmp/path/1.0")

    def test_resolve_dependency_constraints_to_dependencies(self, patch_requests_get):
        """Test that dependency constraints are correctly resolved to specific versions."""
        matrix = ImageMatrix(
            values={"go_version": ["1.24", "1.25"]},
            dependencyConstraints=[
                {
                    "dependency": "python",
                    "constraint": {"latest": True, "count": 2},
                },
                {
                    "dependency": "R",
                    "constraint": {"max": "4.2", "count": 3},
                },
                {
                    "dependency": "quarto",
                    "constraint": {"latest": True},
                    "prerelease": False,
                },
            ],
        )

        assert len(matrix.dependencies) == 3

        python_dep = next(dep for dep in matrix.dependencies if dep.dependency == "python")
        assert isinstance(python_dep, PythonDependencyVersions)
        assert python_dep.versions == ["3.13.7", "3.12.11"]

        r_dep = next(dep for dep in matrix.dependencies if dep.dependency == "R")
        assert isinstance(r_dep, RDependencyVersions)
        assert r_dep.versions == ["4.2.3", "4.1.3", "4.0.5"]

        quarto_dep = next(dep for dep in matrix.dependencies if dep.dependency == "quarto")
        assert isinstance(quarto_dep, QuartoDependencyVersions)
        assert quarto_dep.versions == ["1.7.34"]
