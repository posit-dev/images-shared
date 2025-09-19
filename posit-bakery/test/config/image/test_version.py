from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from posit_bakery.config import ImageVersion, Image, Registry

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestImageVersion:
    def test_name_required(self, caplog):
        """Test that an ImageVersion object requires a name."""
        with pytest.raises(ValidationError, match="Field required"):
            ImageVersion()
        assert "WARNING" not in caplog.text

    def test_name_only(self):
        """Test creating an ImageVersion object with only the name does not raise an exception.

        Test that the default values for subpath, latest, registries, ephemeral, isDevelopmentVersion, and os are set
        correctly.
        """
        i = ImageVersion(name="1.0.0")

        assert i.parent is None
        assert i.subpath == "1.0.0"
        assert not i.latest
        assert len(i.all_registries) == 0
        assert not i.ephemeral
        assert not i.isDevelopmentVersion
        assert len(i.os) == 0

    def test_valid(self):
        """Test creating a valid ImageVersion object with all fields.

        Test that ImageVersionOS objects are correctly initialized and parented.
        """
        i = ImageVersion(
            name="1.0.0",
            subpath="1.0",
            extraRegistries=[
                {"host": "registry1.example.com", "namespace": "namespace1"},
                {"host": "registry2.example.com", "namespace": "namespace2"},
            ],
            latest=True,
            os=[{"name": "Ubuntu 22.04", "primary": True}, {"name": "Ubuntu 24.04"}],
            dependencies=[
                {"dependency": "R", "versions": ["4.5.1", "4.4.3"]},
                {"dependency": "python", "versions": ["3.13.7", "3.12.11"]},
                {"dependency": "quarto", "versions": ["1.8.24"]},
            ],
        )

        assert i.latest
        assert len(i.all_registries) == 2
        assert len(i.os) == 2
        for os in i.os:
            assert os.parent is i

    def test_deduplicate_registries(self, caplog):
        """Test that duplicate registries are deduplicated."""
        i = ImageVersion(
            name="1.0.0",
            extraRegistries=[
                {"host": "registry1.example.com", "namespace": "namespace1"},
                {"host": "registry1.example.com", "namespace": "namespace1"},  # Duplicate
            ],
        )
        assert len(i.all_registries) == 1
        assert i.all_registries[0].host == "registry1.example.com"
        assert i.all_registries[0].namespace == "namespace1"
        assert "WARNING" in caplog.text
        assert (
            "Duplicate registry defined in config for version '1.0.0': registry1.example.com/namespace1" in caplog.text
        )

    def test_check_os_not_empty(self, caplog):
        """Test that an ImageVersion must have at least one OS defined."""
        ImageVersion(name="1.0.0", os=[])
        assert "WARNING" in caplog.text
        assert (
            "No OSes defined for image version '1.0.0'. At least one OS should be defined for complete tagging and "
            "labeling of images." in caplog.text
        )

    def test_deduplicate_os(self, caplog):
        """Test that duplicate OSes are deduplicated."""
        mock_parent = MagicMock(spec=Image)
        mock_parent.path = Path("/tmp/path")
        i = ImageVersion(
            parent=mock_parent,
            name="1.0.0",
            os=[
                {"name": "Ubuntu 22.04", "primary": True},
                {"name": "Ubuntu 22.04"},  # Duplicate
            ],
        )
        assert len(i.os) == 1
        assert i.os[0].name == "Ubuntu 22.04"
        assert "WARNING" in caplog.text
        assert "Duplicate OS defined in config for image version '1.0.0': Ubuntu 22.04" in caplog.text

    def test_make_single_os_primary(self, caplog):
        """Test that if only one OS is defined, it is automatically made primary."""
        i = ImageVersion(name="1.0.0", os=[{"name": "Ubuntu 22.04"}])
        assert len(i.os) == 1
        assert i.os[0].primary is True
        assert i.os[0].name == "Ubuntu 22.04"
        assert "WARNING" not in caplog.text

    def test_max_one_primary_os(self):
        """Test that an error is raised if multiple primary OSes are defined."""
        with pytest.raises(
            ValidationError,
            match="Only one OS can be marked as primary for image version '1.0.0'. Found 2 OSes marked primary.",
        ):
            ImageVersion(
                name="1.0.0",
                os=[
                    {"name": "Ubuntu 22.04", "primary": True},
                    {"name": "Ubuntu 24.04", "primary": True},  # Multiple primary OSes
                ],
            )

    def test_no_primary_os_warning(self, caplog):
        """Test that a warning is logged if no primary OS is defined."""
        ImageVersion(name="1.0.0", os=[{"name": "Ubuntu 22.04"}, {"name": "Ubuntu 24.04"}])
        assert "WARNING" in caplog.text
        assert (
            "No OS marked as primary for image version '1.0.0'. At least one OS should be marked as primary for "
            "complete tagging and labeling of images." in caplog.text
        )

    def test_check_duplicate_dependencies(self):
        """Test an error is raised if duplicate dependencies are defined."""
        with pytest.raises(
            ValidationError,
            match="Duplicate dependencies found in image",
        ):
            ImageVersion(
                name="1.0.0",
                dependencies=[
                    {"dependency": "R", "versions": ["4.2.3", "4.3.3"]},
                    {"dependency": "R", "versions": ["4.3.0"]},  # Duplicate dependency
                ],
            )

    def test_extra_registries_or_override_registries(self):
        """Test that only one of extraRegistries or overrideRegistries can be defined."""
        with pytest.raises(
            ValidationError,
            match="Only one of 'extraRegistries' or 'overrideRegistries' can be defined for image version '1.0.0'.",
        ):
            ImageVersion(
                name="1.0.0",
                extraRegistries=[{"host": "registry.example.com", "namespace": "namespace"}],
                overrideRegistries=[{"host": "another.registry.com", "namespace": "another_namespace"}],
            )

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

    def test_all_registries(self):
        """Test that merged_registries returns the correct list of registries for object and parents."""
        expected_registries = [
            Registry(host="docker.io", namespace="posit"),
            Registry(host="ghcr.io", namespace="posit-dev"),
            Registry(host="ghcr.io", namespace="posit-team"),
            Registry(host="registry1.example.com", namespace="namespace1"),
        ]

        mock_image_parent = MagicMock(spec=Image)
        mock_image_parent.all_registries = [
            expected_registries[0],  # docker.io/posit
            expected_registries[1],  # ghcr.io/posit-dev
            expected_registries[2],  # ghcr.io/posit-team
        ]
        i = ImageVersion(
            parent=mock_image_parent,
            name="1.0.0",
            extraRegistries=[
                expected_registries[3],  # registry1.example.com/namespace1
                expected_registries[0],  # docker.io/posit
            ],
        )

        assert len(i.all_registries) == 4
        for registry in expected_registries:
            assert registry in i.all_registries

    def test_all_registries_with_override(self):
        """Test that merged_registries returns the correct list of registries when overridden."""
        parent_registries = [
            Registry(host="docker.io", namespace="posit"),
            Registry(host="ghcr.io", namespace="posit-dev"),
            Registry(host="ghcr.io", namespace="posit-team"),
        ]
        override_registries = [
            Registry(host="ghcr.io", namespace="posit-team"),
            Registry(host="registry1.example.com", namespace="namespace1"),
        ]

        mock_image_parent = MagicMock(spec=Image)
        mock_image_parent.merged_registries = parent_registries
        i = ImageVersion(
            parent=mock_image_parent,
            name="1.0.0",
            overrideRegistries=override_registries,
        )

        assert len(i.all_registries) == 2
        for registry in override_registries:
            assert registry in i.all_registries
