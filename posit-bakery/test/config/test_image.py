from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from posit_bakery.config.config import BakeryConfigDocument
from posit_bakery.config.image import ImageVersionOS, ImageVersion, Image, ImageVariant
from posit_bakery.config.registry import Registry


class TestImageVersionOS:
    def test_valid_name_only(self):
        """Test creating an ImageVersionOS object with only the name does not raise an exception.

        Test that the default values for extension and tagDisplayName are set correctly.
        Test that the primary field defaults to False.
        """
        i = ImageVersionOS(name="Ubuntu 22.04")

        assert not i.primary
        assert i.extension == "ubuntu2204"
        assert i.tagDisplayName == "ubuntu-22.04"

    def test_valid(self):
        """Test creating a valid ImageVersionOS object with all fields."""
        ImageVersionOS(name="Ubuntu 22.04", extension="ubuntu", tagDisplayName="jammy", primary=True)

    def test_extension_validation(self):
        """Test that the extension field only allows alphanumeric characters, underscores, and hyphens."""
        with pytest.raises(ValidationError):
            ImageVersionOS(name="Ubuntu 22.04", extension="invalid_extension!")

    def test_tag_display_name_validation(self):
        """Test that the tagDisplayName field only allows alphanumeric characters, underscores, hyphens, and periods."""
        with pytest.raises(ValidationError):
            ImageVersionOS(name="Ubuntu 22.04", tagDisplayName="invalid tag name!")


class TestImageVersion:
    def test_name_only(self):
        """Test creating an ImageVersion object with only the name does not raise an exception.

        Test that the default values for subpath, latest, registries, and os are set correctly.
        """
        i = ImageVersion(name="1.0.0")

        assert i.parent is None
        assert i.subpath == "1.0.0"
        assert not i.latest
        assert len(i.registries) == 0
        assert len(i.os) == 0

    def test_valid(self):
        """Test creating a valid ImageVersion object with all fields.

        Test that ImageVersionOS objects are correctly initialized and parented.
        """
        i = ImageVersion(
            name="1.0.0",
            subpath="1.0",
            registries=[
                {"host": "registry1.example.com", "namespace": "namespace1"},
                {"host": "registry2.example.com", "namespace": "namespace2"},
            ],
            latest=True,
            os=[{"name": "Ubuntu 22.04", "primary": True}, {"name": "Ubuntu 24.04"}],
        )

        assert i.latest
        assert len(i.registries) == 2
        assert len(i.os) == 2
        for os in i.os:
            assert os.parent is i

    def test_path_resolution(self):
        """Test that the path property resolves correctly based on the parent image's path and subpath."""
        mock_parent = MagicMock(spec=Image)
        mock_parent.path = Path("/tmp/path")
        i = ImageVersion(
            parent=mock_parent,
            name="1.0.0",
        )
        assert i.path == Path("/tmp/path/1.0.0")

        i.subpath = "1.0"
        assert i.path == Path("/tmp/path/1.0")

    def test_merged_registries(self):
        """Test that merged_registries returns the correct list of registries for object and parents."""
        expected_registries = [
            Registry(host="docker.io", namespace="posit"),
            Registry(host="ghcr.io", namespace="posit-dev"),
            Registry(host="ghcr.io", namespace="posit-team"),
            Registry(host="registry1.example.com", namespace="namespace1"),
        ]

        mock_config_parent = MagicMock(spec=BakeryConfigDocument)
        mock_config_parent.registries = [
            expected_registries[0],  # docker.io/posit
            expected_registries[1],  # ghcr.io/posit-dev
        ]
        mock_image_parent = MagicMock(spec=Image)
        mock_image_parent.parent = mock_config_parent
        mock_image_parent.registries = [
            expected_registries[1],  # ghcr.io/posit-dev
            expected_registries[2],  # ghcr.io/posit-team
        ]
        i = ImageVersion(
            parent=mock_image_parent,
            name="1.0.0",
            registries=[
                expected_registries[3],  # registry1.example.com/namespace1
                expected_registries[0],  # docker.io/posit
            ],
        )

        assert len(i.merged_registries) == 4
        for registry in expected_registries:
            assert registry in i.merged_registries


class TestImageVariant:
    def test_valid(self):
        """Test creating a valid ImageVariant object does not raise an exception."""
        i = ImageVariant(name="Variant 1")

        assert i.parent is None
        assert i.name == "Variant 1"
        assert i.extension == "variant1"
        assert i.tagDisplayName == "variant-1"
        assert len(i.tags) == 0
        assert len(i.options) == 1

    def test_custom_options(self):
        """Test creating an ImageVariant with custom options."""
        custom_options = [{"tool": "goss", "wait": 10, "command": "/bin/bash -c 'my command'"}]
        i = ImageVariant(name="Custom Goss", options=custom_options)

        assert len(i.options) == 1
        assert i.options[0].tool == "goss"
        assert i.options[0].wait == 10
        assert i.options[0].command == "/bin/bash -c 'my command'"

    def test_extension_validation(self):
        """Test that the extension field only allows alphanumeric characters, underscores, and hyphens."""
        with pytest.raises(ValidationError):
            ImageVariant(name="Standard", extension="invalid_extension!")

    def test_tag_display_name_validation(self):
        """Test that the tagDisplayName field only allows alphanumeric characters, underscores, hyphens, and periods."""
        with pytest.raises(ValidationError):
            ImageVariant(name="Standard", tagDisplayName="invalid tag name!")
