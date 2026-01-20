import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from posit_bakery.config import Image, BakeryConfigDocument, BaseRegistry, Registry, ImageVersion
from posit_bakery.config.dependencies.python import PythonDependencyVersions
from posit_bakery.config.dependencies.quarto import QuartoDependencyVersions
from posit_bakery.config.dependencies.r import RDependencyVersions
from posit_bakery.config.image.posit_product.main import ReleaseStreamResult

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestImage:
    def test_name_required(self, caplog):
        """Test that an Image object requires a name."""
        with pytest.raises(ValidationError, match="Field required"):
            Image()
        assert "WARNING" not in caplog.text

    def test_required_fields(self):
        """Test creating an Image object with only the name does not raise an exception.

        Test that the default values for subpath, registries, tagPatterns, and variants are set correctly.
        Test that parentage is set
        """
        i = Image(name="my-image", versions=[{"name": "1.0.0"}])

        assert i.parent is None
        assert i.subpath == "my-image"
        assert len(i.extraRegistries) == 0
        assert len(i.tagPatterns) == 8
        assert len(i.variants) == 0
        assert len(i.versions) == 1
        for version in i.versions:
            assert version.parent is i

    def test_valid(self):
        """Test creating a valid Image object with all fields."""
        i = Image(
            name="my-image",
            subpath="my-image-subpath",
            extraRegistries=[{"host": "registry.example.com", "namespace": "namespace"}],
            tagPatterns=[{"patterns": ["{{ Version }}-{{ OS }}-{{ Variant }}"]}],
            variants=[{"name": "Standard"}],
            versions=[{"name": "1.0.0"}],
            dependencyConstraints=[
                {"dependency": "R", "constraint": {"latest": True, "count": 1}},
                {"dependency": "python", "constraint": {"latest": True, "count": 1}},
                {"dependency": "quarto", "constraint": {"latest": True, "count": 1}},
            ],
        )

        assert i.name == "my-image"
        assert i.displayName == "My Image"
        assert i.subpath == "my-image-subpath"
        assert len(i.extraRegistries) == 1
        assert len(i.tagPatterns) == 1
        assert len(i.variants) == 1
        assert len(i.versions) == 1

    def test_documentation_url_https_prepend(self):
        """Test that the documentation URL is correctly prepended with https:// if missing."""
        i = Image(name="my-image", documentationUrl="docs.example.com", versions=[{"name": "1.0.0"}])
        assert str(i.documentationUrl) == "https://docs.example.com/"

        i = Image(name="my-image", documentationUrl="http://docs.example.com", versions=[{"name": "1.0.0"}])
        assert str(i.documentationUrl) == "http://docs.example.com/"

        i = Image(name="my-image", documentationUrl="https://docs.example.com", versions=[{"name": "1.0.0"}])
        assert str(i.documentationUrl) == "https://docs.example.com/"

    def test_deduplicate_registries(self, caplog):
        """Test that duplicate registries are deduplicated."""
        i = Image(
            name="my-image",
            extraRegistries=[
                {"host": "registry.example.com", "namespace": "namespace"},
                {"host": "registry.example.com", "namespace": "namespace"},  # Duplicate
            ],
            versions=[{"name": "1.0.0"}],
        )
        assert len(i.extraRegistries) == 1
        assert i.extraRegistries[0].host == "registry.example.com"
        assert i.extraRegistries[0].namespace == "namespace"
        assert "WARNING" in caplog.text
        assert (
            "Duplicate registry defined in config for image 'my-image': registry.example.com/namespace" in caplog.text
        )

    def test_extra_registries_or_override_registries(self):
        """Test that only one of extraRegistries or overrideRegistries can be defined."""
        with pytest.raises(
            ValidationError,
            match="Only one of 'extraRegistries' or 'overrideRegistries' can be defined for image 'my-image'.",
        ):
            Image(
                name="my-image",
                extraRegistries=[{"host": "registry.example.com", "namespace": "namespace"}],
                overrideRegistries=[{"host": "another.registry.com", "namespace": "another_namespace"}],
                versions=[{"name": "1.0.0"}],
            )

    def test_check_duplicate_dependency_constraints(self):
        """Test that a ValidationError is raised if multiple dependencyConstraints of the same type are defined."""
        with pytest.raises(
            ValidationError,
            match="Duplicate dependency constraints found in image",
        ):
            Image(
                name="my-image",
                dependencyConstraints=[
                    {"dependency": "R", "constraint": {"latest": True, "count": 2}},
                    {"dependency": "R", "constraint": {"max": "4.3", "count": 1}},  # Duplicate
                ],
                versions=[{"name": "1.0.0"}],
            )

    def test_check_not_empty(self, caplog):
        """Test that an Image must have at least one version defined."""
        Image(name="my-image", versions=[], devVersions=[], matrix=None)
        assert "WARNING" in caplog.text
        assert (
            "No versions, devVersions, or matrix found in image 'my-image'. At least one is required for most commands."
            in caplog.text
        )

    def test_check_version_duplicates(self):
        """Test that an error is raised if duplicate version names are found."""
        with pytest.raises(ValidationError, match="Duplicate versions found in image 'my-image':\n - 1.0.0"):
            Image(
                name="my-image",
                versions=[{"name": "1.0.0"}, {"name": "1.0.0"}],  # Duplicate version names
            )

    def test_check_variant_duplicates(self):
        """Test that an error is raised if duplicate variant names are found."""
        with pytest.raises(ValidationError, match="Duplicate variants found in image 'my-image':\n - Standard"):
            Image(
                name="my-image",
                variants=[{"name": "Standard"}, {"name": "Standard"}],  # Duplicate variant names
                versions=[{"name": "1.0.0"}],
            )

    def test_resolve_parentage(self):
        """Test that parentage is correctly resolved for versions and variants."""
        i = Image(name="my-image", versions=[{"name": "1.0.0"}], variants=[{"name": "Standard"}])

        assert i.parent is None
        for version in i.versions:
            assert version.parent is i
        for variant in i.variants:
            assert variant.parent is i

    def test_check_dependency_constraints_with_matrix(self, caplog):
        i = Image(
            name="my-image",
            dependencyConstraints=[{"dependency": "R", "constraint": {"latest": True, "count": 2}}],
            matrix={"dependencyConstraints": [{"dependency": "python", "constraint": {"latest": True, "count": 2}}]},
        )
        assert "WARNING" in caplog.text
        assert "defines both 'dependencyConstraints' and a 'matrix'" in caplog.text

    def test_path_resolution(self):
        """Test that the path property resolves correctly based on the parent image's path and subpath."""
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = Path("/tmp/path")
        i = Image(parent=mock_parent, name="my-image", versions=[{"name": "1.0.0"}])
        assert i.path == Path("/tmp/path/my-image")

        i.subpath = "my-image-subpath"
        assert i.path == Path("/tmp/path/my-image-subpath")

    def test_all_registries(self):
        """Test that merged_registries returns the correct list of registries for object and parents."""
        expected_registries = [
            BaseRegistry(host="docker.io", namespace="posit"),
            BaseRegistry(host="ghcr.io", namespace="posit-dev"),
            BaseRegistry(host="ghcr.io", namespace="posit-team"),
        ]

        mock_config_parent = MagicMock(spec=BakeryConfigDocument)
        mock_config_parent.registries = [
            expected_registries[0],  # docker.io/posit
            expected_registries[1],  # ghcr.io/posit-dev
        ]
        i = Image(
            parent=mock_config_parent,
            name="my-image",
            versions=[{"name": "1.0.0"}],
            extraRegistries=[expected_registries[1], expected_registries[2]],  # registry.example.com/namespace
        )

        assert len(i.all_registries) == 3
        for registry in expected_registries:
            assert registry in i.all_registries

    def test_extra_registries_with_repository_field(self):
        """Test that all_registries returns the correct list of registries when extraRegistries with repository field is defined."""
        parent_registries = [
            BaseRegistry(host="docker.io", namespace="posit"),
            BaseRegistry(host="ghcr.io", namespace="posit-dev"),
        ]
        expected_registries = [
            BaseRegistry(host="docker.io", namespace="posit"),
            BaseRegistry(host="ghcr.io", namespace="posit-dev"),
            Registry(host="ghcr.io", namespace="posit-dev", repository="custom-repo"),
        ]

        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.registries = parent_registries
        i = Image(
            parent=mock_parent,
            name="my-image",
            versions=[{"name": "1.0.0"}],
            extraRegistries=[{"host": "ghcr.io", "namespace": "posit-dev", "repository": "custom-repo"}],
        )

        assert len(i.all_registries) == 3
        for registry in expected_registries:
            assert registry in i.all_registries

    def test_override_registries_with_repository_field(self):
        """Test that all_registries returns the correct list of registries when overrideRegistries with repository field is defined."""
        parent_registries = [
            BaseRegistry(host="docker.io", namespace="posit"),
            BaseRegistry(host="ghcr.io", namespace="posit-dev"),
        ]
        expected_registries = [
            Registry(host="ghcr.io", namespace="posit-dev", repository="custom-repo"),
        ]

        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.registries = parent_registries
        i = Image(
            parent=mock_parent,
            name="my-image",
            versions=[{"name": "1.0.0"}],
            overrideRegistries=[{"host": "ghcr.io", "namespace": "posit-dev", "repository": "custom-repo"}],
        )
        assert len(i.all_registries) == 1
        for registry in expected_registries:
            assert registry in i.all_registries

    def test_resolve_dependency_versions(self, patch_requests_get):
        """Test that dependency constraints are correctly resolved to specific versions."""
        i = Image(
            name="my-image",
            versions=[{"name": "1.0.0"}],
            dependencyConstraints=[
                {"dependency": "R", "constraint": {"latest": True, "count": 2}},
                {"dependency": "python", "constraint": {"max": "3.12", "count": 2}},
                {"dependency": "quarto", "constraint": {"latest": True}},
            ],
        )

        resolved = i.resolve_dependency_versions()

        assert len(resolved) == 3
        assert resolved[0] == RDependencyVersions(versions=["4.5.1", "4.4.3"])
        assert resolved[1] == PythonDependencyVersions(versions=["3.12.11", "3.11.13"])
        assert resolved[2] == QuartoDependencyVersions(versions=["1.7.34"])

    def test_get_version(self):
        """Test that get_version returns the correct version object by name."""
        i = Image(name="my-image", versions=[{"name": "1.0.0"}, {"name": "2.0.0"}])

        version = i.get_version("1.0.0")
        assert version.name == "1.0.0"

        version = i.get_version("2.0.0")
        assert version.name == "2.0.0"

        assert i.get_version("non-existent") is None

    def test_get_variant(self):
        """Test that get_variant returns the correct variant object by name."""
        i = Image(name="my-image", variants=[{"name": "Standard"}, {"name": "Minimal"}])

        variant = i.get_variant("Standard")
        assert variant.name == "Standard"

        variant = i.get_variant("Minimal")
        assert variant.name == "Minimal"

        assert i.get_variant("non-existent") is None

    def test_create_version(self):
        """Test that create_version creates a new version and adds it to the image."""
        i = Image(name="my-image")
        new_version = i.create_version("1.0.0")

        assert new_version.name == "1.0.0"
        assert len(i.versions) == 1
        assert i.versions[0] is new_version
        assert new_version.parent is i

    def test_create_version_with_dependencies(self, patch_requests_get):
        """Test that create_version creates a new version with dependencies when dependency constraints are defined."""
        i = Image(
            name="my-image",
            dependencyConstraints=[
                {"dependency": "R", "constraint": {"latest": True}},
                {"dependency": "python", "constraint": {"latest": True}},
                {"dependency": "quarto", "constraint": {"latest": True}},
            ],
        )
        new_version = i.create_version("1.0.0")

        assert new_version.name == "1.0.0"
        assert len(i.versions) == 1
        assert i.versions[0] is new_version
        assert new_version.parent is i
        assert len(new_version.dependencies) == 3
        assert new_version.dependencies[0] == RDependencyVersions(versions=["4.5.1"])
        assert new_version.dependencies[1] == PythonDependencyVersions(versions=["3.13.7"])
        assert new_version.dependencies[2] == QuartoDependencyVersions(versions=["1.7.34"])

    def test_create_version_model_existing_version(self):
        """Test that create_version raises an error if the version already exists."""
        i = Image(name="my-image", versions=[{"name": "1.0.0"}])

        with pytest.raises(ValueError, match="Version '1.0.0' already exists in image 'my-image'."):
            i.create_version("1.0.0")

    def test_create_version_existing_version_update(self):
        """Test that create_version updates an existing version if it already exists."""
        i = Image(name="my-image", versions=[{"name": "1.0.0"}, {"name": "2.0.0", "latest": True}])
        updated_version = i.create_version("1.0.0", subpath="updated-subpath", update_if_exists=True)

        assert updated_version.name == "1.0.0"
        assert updated_version.subpath == "updated-subpath"
        assert updated_version.latest is True
        assert len(i.versions) == 2
        assert i.versions[0] is updated_version
        assert not i.versions[1].latest
        assert updated_version.parent is i

    def test_patch_version(self, get_tmpcontext, common_image_variants_objects):
        """Test that patch_version patches an existing version and updates files."""
        context = get_tmpcontext("basic")
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [BaseRegistry(host="docker.io", namespace="posit")]

        i = Image(
            name="test-image", versions=[{"name": "1.0.0"}], variants=common_image_variants_objects, parent=mock_parent
        )
        i.patch_version("1.0.0", "1.0.1")

        # Check that the version was updated in the model
        assert i.versions[0].name == "1.0.1"

        # Check that the version files were updated
        expected_path = context / "test-image" / "1.0.1"
        assert expected_path.exists() and expected_path.is_dir()
        assert (expected_path / "Containerfile.ubuntu2204.std").is_file()
        assert (expected_path / "Containerfile.ubuntu2204.min").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (expected_path / "Containerfile.ubuntu2204.std").read_text()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (expected_path / "Containerfile.ubuntu2204.min").read_text()
        assert (expected_path / "deps").is_dir()
        assert (expected_path / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (expected_path / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (expected_path / "test").is_dir()
        assert (expected_path / "test" / "goss.yaml").is_file()

    def test_patch_version_test_clean(self, get_tmpcontext, common_image_variants_objects):
        """Test that files are removed by patch_version when clean=True."""
        context = get_tmpcontext("basic")
        original_version_path = context / "test-image" / "1.0.0"
        (original_version_path / "extra-file.txt").write_text("This is an extra file that should be removed.")

        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [BaseRegistry(host="docker.io", namespace="posit")]

        i = Image(
            name="test-image", versions=[{"name": "1.0.0"}], variants=common_image_variants_objects, parent=mock_parent
        )
        i.patch_version("1.0.0", "1.0.1")

        # Check that the version was updated in the model
        assert i.versions[0].name == "1.0.1"

        # Check that the extra file was removed
        assert not (context / "test-image" / "1.0.1" / "extra-file.txt").exists()

        # Check that the version files were updated
        expected_path = context / "test-image" / "1.0.1"
        assert expected_path.exists() and expected_path.is_dir()
        assert (expected_path / "Containerfile.ubuntu2204.std").is_file()
        assert (expected_path / "Containerfile.ubuntu2204.min").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (expected_path / "Containerfile.ubuntu2204.std").read_text()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (expected_path / "Containerfile.ubuntu2204.min").read_text()
        assert (expected_path / "deps").is_dir()
        assert (expected_path / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (expected_path / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (expected_path / "test").is_dir()
        assert (expected_path / "test" / "goss.yaml").is_file()

    def test_patch_version_test_no_clean(self, get_tmpcontext, common_image_variants_objects):
        """Test that files are preserved by patch_version when clean=False."""
        context = get_tmpcontext("basic")
        original_version_path = context / "test-image" / "1.0.0"
        (original_version_path / "extra-file.txt").write_text("This is an extra file that should be removed.")

        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [BaseRegistry(host="docker.io", namespace="posit")]

        i = Image(
            name="test-image", versions=[{"name": "1.0.0"}], variants=common_image_variants_objects, parent=mock_parent
        )
        i.patch_version("1.0.0", "1.0.1", clean=False)

        # Check that the version was updated in the model
        assert i.versions[0].name == "1.0.1"

        # Check that the extra file was preserved
        assert (context / "test-image" / "1.0.1" / "extra-file.txt").exists()

        # Check that the version files were updated
        expected_path = context / "test-image" / "1.0.1"
        assert expected_path.exists() and expected_path.is_dir()
        assert (expected_path / "Containerfile.ubuntu2204.std").is_file()
        assert (expected_path / "Containerfile.ubuntu2204.min").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (expected_path / "Containerfile.ubuntu2204.std").read_text()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (expected_path / "Containerfile.ubuntu2204.min").read_text()
        assert (expected_path / "deps").is_dir()
        assert (expected_path / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (expected_path / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (expected_path / "test").is_dir()
        assert (expected_path / "test" / "goss.yaml").is_file()

    def test_patch_version_test_clean_with_subpath(self, get_tmpcontext, common_image_variants_objects):
        """Test that files are removed by patch_version when clean=True and a subpath is in use."""
        context = get_tmpcontext("basic")
        original_version_path = context / "test-image" / "1.0.0"
        subpathed_path = context / "test-image" / "1.0"
        shutil.move(original_version_path, subpathed_path)
        (subpathed_path / "extra-file.txt").write_text("This is an extra file that should be removed.")

        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [BaseRegistry(host="docker.io", namespace="posit")]

        i = Image(
            name="test-image",
            versions=[{"name": "1.0.0", "subpath": "1.0"}],
            variants=common_image_variants_objects,
            parent=mock_parent,
        )
        i.patch_version("1.0.0", "1.0.1")

        # Check that the version was updated in the model
        assert i.versions[0].name == "1.0.1"

        # Check that the extra file was removed
        assert not (subpathed_path / "extra-file.txt").exists()

        # Check that the version files were updated
        assert subpathed_path.exists() and subpathed_path.is_dir()
        assert (subpathed_path / "Containerfile.ubuntu2204.std").is_file()
        assert (subpathed_path / "Containerfile.ubuntu2204.min").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (subpathed_path / "Containerfile.ubuntu2204.std").read_text()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (subpathed_path / "Containerfile.ubuntu2204.min").read_text()
        assert (subpathed_path / "deps").is_dir()
        assert (subpathed_path / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (subpathed_path / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (subpathed_path / "test").is_dir()
        assert (subpathed_path / "test" / "goss.yaml").is_file()

    def test_patch_version_test_no_clean_with_subpath(self, get_tmpcontext, common_image_variants_objects):
        """Test that files are preserved by patch_version when clean=False and a subpath is in use."""
        context = get_tmpcontext("basic")
        original_version_path = context / "test-image" / "1.0.0"
        subpathed_path = context / "test-image" / "1.0"
        shutil.move(original_version_path, subpathed_path)
        (subpathed_path / "extra-file.txt").write_text("This is an extra file that should be removed.")

        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [BaseRegistry(host="docker.io", namespace="posit")]

        i = Image(
            name="test-image",
            versions=[{"name": "1.0.0", "subpath": "1.0"}],
            variants=common_image_variants_objects,
            parent=mock_parent,
        )
        i.patch_version("1.0.0", "1.0.1")

        # Check that the version was updated in the model
        assert i.versions[0].name == "1.0.1"

        # Check that the extra file was removed
        assert not (subpathed_path / "extra-file.txt").exists()

        # Check that the version files were updated
        assert subpathed_path.exists() and subpathed_path.is_dir()
        assert (subpathed_path / "Containerfile.ubuntu2204.std").is_file()
        assert (subpathed_path / "Containerfile.ubuntu2204.min").is_file()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (subpathed_path / "Containerfile.ubuntu2204.std").read_text()
        assert 'ARG IMAGE_VERSION="1.0.1"' in (subpathed_path / "Containerfile.ubuntu2204.min").read_text()
        assert (subpathed_path / "deps").is_dir()
        assert (subpathed_path / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (subpathed_path / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (subpathed_path / "test").is_dir()
        assert (subpathed_path / "test" / "goss.yaml").is_file()

    def test_patch_version_old_version_does_not_exist(self, get_tmpcontext, common_image_variants_objects):
        """Test that patch_version patches an existing version and updates files."""
        context = get_tmpcontext("basic")
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [BaseRegistry(host="docker.io", namespace="posit")]

        i = Image(
            name="test-image", versions=[{"name": "1.0.0"}], variants=common_image_variants_objects, parent=mock_parent
        )
        with pytest.raises(ValueError, match="Version '2.0.0' does not exist for image 'test-image'."):
            i.patch_version("2.0.0", "2.0.1")

    def test_patch_version_new_version_already_exists(self, get_tmpcontext, common_image_variants_objects):
        """Test that patch_version patches an existing version and updates files."""
        context = get_tmpcontext("basic")
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [BaseRegistry(host="docker.io", namespace="posit")]

        i = Image(
            name="test-image", versions=[{"name": "1.0.0"}], variants=common_image_variants_objects, parent=mock_parent
        )
        with pytest.raises(ValueError, match="Version '1.0.0' already exists in image 'test-image'."):
            i.patch_version("1.0.0", "1.0.0")

    def test_create_matrix(self):
        """Test that create_version creates a new version and adds it to the image."""
        i = Image(name="my-image")
        matrix = i.create_matrix(
            dependency_constraints=[
                {"dependency": "R", "constraint": {"latest": True, "count": 2}},
                {"dependency": "python", "constraint": {"latest": True, "count": 2}},
                {"dependency": "quarto", "constraint": {"latest": True}},
            ]
        )

        assert (
            matrix.namePattern
            == "R{{ Dependencies.R }}-python{{ Dependencies.python }}-quarto{{ Dependencies.quarto }}"
        )
        assert i.matrix is matrix
        assert matrix.parent is i
        assert len(matrix.resolved_dependencies) == 3

    def test_create_matrix_existing_versions(self):
        """Test that create_matrix raises an error if a version already exists."""
        i = Image(name="my-image", versions=[{"name": "1.0.0"}])

        with pytest.raises(ValueError, match="Cannot create matrix version for image"):
            i.create_matrix(
                dependency_constraints=[
                    {"dependency": "R", "constraint": {"latest": True, "count": 2}},
                    {"dependency": "python", "constraint": {"latest": True, "count": 2}},
                    {"dependency": "quarto", "constraint": {"latest": True}},
                ]
            )

    def test_create_matrix_existing_matrix(self):
        """Test that create_matrix raises an error if a matrix already exists."""
        i = Image(
            name="my-image",
            matrix={"dependencyConstraints": [{"dependency": "quarto", "constraint": {"latest": True}}]},
        )

        with pytest.raises(ValueError, match="Matrix already defined"):
            i.create_matrix(
                dependency_constraints=[
                    {"dependency": "R", "constraint": {"latest": True, "count": 2}},
                    {"dependency": "python", "constraint": {"latest": True, "count": 2}},
                    {"dependency": "quarto", "constraint": {"latest": True}},
                ]
            )

    def test_create_matrix_existing_matrix_update_existing(self):
        """Test that create_matrix updates a matrix the update_if_exists option."""
        i = Image(
            name="my-image",
            matrix={"dependencyConstraints": [{"dependency": "quarto", "constraint": {"latest": True}}]},
        )
        assert len(i.matrix.resolved_dependencies) == 1

        i.create_matrix(
            dependency_constraints=[
                {"dependency": "R", "constraint": {"latest": True, "count": 2}},
                {"dependency": "python", "constraint": {"latest": True, "count": 2}},
                {"dependency": "quarto", "constraint": {"latest": True}},
            ],
            update_if_exists=True,
        )
        assert len(i.matrix.resolved_dependencies) == 3

    def test_load_dev_versions(self):
        """Test that load_dev_versions correctly loads development versions from configured devVersions."""
        context = Path(__file__).parent.parent.parent / "contexts" / "with-dev-versions"
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context

        env_version = "1.0.1"
        env_url = "https://example.com/image.tar.gz"
        stream_version = "1.1.0"
        stream_url = "https://example.com/image-daily.tar.gz"
        with patch.dict(os.environ, {"VERSION_ENV_VAR": env_version, "URL_ENV_VAR": env_url}, clear=True):
            with patch("posit_bakery.config.image.dev_version.stream.get_product_artifact_by_stream") as mock_get:
                mock_get.return_value = ReleaseStreamResult(version=stream_version, download_url=stream_url)
                i = Image(
                    name="my-image",
                    parent=mock_parent,
                    devVersions=[
                        {
                            "sourceType": "env",
                            "versionEnvVar": "VERSION_ENV_VAR",
                            "urlEnvVar": "URL_ENV_VAR",
                            "os": [
                                {"name": "Ubuntu 22.04", "primary": True},
                            ],
                        },
                        {
                            "sourceType": "stream",
                            "product": "workbench",
                            "stream": "daily",
                            "os": [
                                {"name": "Ubuntu 22.04", "primary": True},
                            ],
                        },
                    ],
                    versions=[{"name": "1.0.0"}],
                )
                i.load_dev_versions()

        assert len(i.versions) == 3
        assert i.get_version("1.0.0") is not None

        assert i.get_version(env_version) is not None
        assert not i.get_version(env_version).latest
        assert i.get_version(env_version).subpath == f".dev-{env_version}"
        assert i.get_version(env_version).ephemeral
        assert i.get_version(env_version).isDevelopmentVersion
        assert len(i.get_version(env_version).os) == 1
        assert i.get_version(env_version).os[0].name == "Ubuntu 22.04"
        assert str(i.get_version(env_version).os[0].artifactDownloadURL) == env_url

        assert i.get_version(stream_version) is not None
        assert not i.get_version(stream_version).latest
        assert i.get_version(stream_version).subpath == f".dev-{stream_version}"
        assert i.get_version(stream_version).ephemeral
        assert i.get_version(stream_version).isDevelopmentVersion
        assert len(i.get_version(stream_version).os) == 1
        assert i.get_version(stream_version).os[0].name == "Ubuntu 22.04"
        assert str(i.get_version(stream_version).os[0].artifactDownloadURL) == stream_url

    def test_render_ephemeral_version_files(self, get_tmpcontext, common_image_variants_objects):
        """Test that render_ephemeral_version_files creates the correct directory structure for an ephemeral version."""
        context = get_tmpcontext("basic")
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [BaseRegistry(host="docker.io", namespace="posit")]

        new_version = ImageVersion(
            name="2.0.0",
            subpath=".dev-2.0.0",
            os=[{"name": "Ubuntu 22.04", "primary": True}],
            ephemeral=True,
            isDevelopmentVersion=True,
        )
        i = Image(
            name="test-image",
            versions=[{"name": "1.0.0"}, new_version],
            variants=common_image_variants_objects,
            parent=mock_parent,
        )

        i.render_ephemeral_version_files()

        expected_path = context / "test-image" / ".dev-2.0.0"
        assert expected_path.exists() and expected_path.is_dir()
        assert (expected_path / "Containerfile.ubuntu2204.min").is_file()
        assert (expected_path / "Containerfile.ubuntu2204.std").is_file()
        assert (expected_path / "deps").is_dir()
        assert (expected_path / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (expected_path / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (expected_path / "test").is_dir()
        assert (expected_path / "test" / "goss.yaml").is_file()

    def test_remove_ephemeral_version_files(self, get_tmpcontext, common_image_variants_objects):
        """Test that create_ephemeral_version_files creates the correct directory structure for an ephemeral version."""
        context = get_tmpcontext("basic")
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [BaseRegistry(host="docker.io", namespace="posit")]

        new_version = ImageVersion(
            name="2.0.0",
            subpath=".dev-2.0.0",
            os=[{"name": "Ubuntu 22.04", "primary": True}],
            ephemeral=True,
            isDevelopmentVersion=True,
        )
        i = Image(
            name="test-image",
            versions=[{"name": "1.0.0"}, new_version],
            variants=common_image_variants_objects,
            parent=mock_parent,
        )

        i.render_ephemeral_version_files()

        expected_path = context / "test-image" / ".dev-2.0.0"
        assert expected_path.exists() and expected_path.is_dir()
        assert (expected_path / "Containerfile.ubuntu2204.min").is_file()
        assert (expected_path / "Containerfile.ubuntu2204.std").is_file()
        assert (expected_path / "deps").is_dir()
        assert (expected_path / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (expected_path / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (expected_path / "test").is_dir()
        assert (expected_path / "test" / "goss.yaml").is_file()

        i.remove_ephemeral_version_files()
        assert not expected_path.exists()
        assert (context / "test-image").exists()
        assert (context / "test-image" / "1.0.0").exists()
