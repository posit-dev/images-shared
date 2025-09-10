from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from posit_bakery.config import Image, BakeryConfigDocument, Registry, ImageVersion

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

    def test_registries_or_override_registries(self):
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

    def test_check_versions_not_empty(self, caplog):
        """Test that an Image must have at least one version defined."""
        Image(name="my-image", versions=[])
        assert "WARNING" in caplog.text
        assert (
            "No versions found in image 'my-image'. At least one version is required for most commands." in caplog.text
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
            Registry(host="docker.io", namespace="posit"),
            Registry(host="ghcr.io", namespace="posit-dev"),
            Registry(host="ghcr.io", namespace="posit-team"),
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

    def test_create_version_files(self, get_tmpcontext):
        """Test that create_version_files creates the correct directory structure."""
        context = get_tmpcontext("basic")
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = context
        mock_parent.registries = [Registry(host="docker.io", namespace="posit")]

        i = Image(name="test-image", versions=[{"name": "1.0.0"}], parent=mock_parent)
        new_version = ImageVersion(
            parent=i,
            name="2.0.0",
            subpath="2.0",
            os=[{"name": "Ubuntu 22.04", "primary": True}],
        )

        Image.create_version_files(new_version, i.variants)

        expected_path = context / "test-image" / "2.0"
        assert expected_path.exists() and expected_path.is_dir()
        assert (expected_path / "Containerfile.ubuntu2204").is_file()
        assert (expected_path / "deps").is_dir()
        assert (expected_path / "deps" / "ubuntu2204_packages.txt").is_file()
        assert (expected_path / "deps" / "ubuntu2204_optional_packages.txt").is_file()
        assert (expected_path / "test").is_dir()
        assert (expected_path / "test" / "goss.yaml").is_file()

    def test_create_version_model(self):
        """Test that create_version creates a new version and adds it to the image."""
        i = Image(name="my-image")
        new_version = i.create_version_model("1.0.0")

        assert new_version.name == "1.0.0"
        assert len(i.versions) == 1
        assert i.versions[0] is new_version
        assert new_version.parent is i

    def test_create_version_model_existing_version(self):
        """Test that create_version raises an error if the version already exists."""
        i = Image(name="my-image", versions=[{"name": "1.0.0"}])

        with pytest.raises(ValueError, match="Version '1.0.0' already exists in image 'my-image'."):
            i.create_version_model("1.0.0")

    def test_create_version_model_existing_version_update(self):
        """Test that create_version updates an existing version if it already exists."""
        i = Image(name="my-image", versions=[{"name": "1.0.0"}, {"name": "2.0.0", "latest": True}])
        updated_version = i.create_version_model("1.0.0", subpath="updated-subpath", update_if_exists=True)

        assert updated_version.name == "1.0.0"
        assert updated_version.subpath == "updated-subpath"
        assert updated_version.latest is True
        assert len(i.versions) == 2
        assert i.versions[0] is updated_version
        assert not i.versions[1].latest
        assert updated_version.parent is i
