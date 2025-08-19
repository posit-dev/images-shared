from pathlib import Path
from unittest.mock import MagicMock

import pytest
from _pytest.mark import ParameterSet
from pydantic import ValidationError

from posit_bakery.config.config import BakeryConfigDocument
from posit_bakery.config.image import ImageVersionOS, ImageVersion, Image, ImageVariant
from posit_bakery.config.registry import Registry
from posit_bakery.config.tools import GossOptions

pytestmark = [
    pytest.mark.unit,
    pytest.mark.config,
]


class TestImageVersionOS:
    def test_name_required(self):
        """Test that an ImageVersionOS object requires a name."""
        with pytest.raises(ValidationError, match="Field required"):
            ImageVersionOS()

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

    def test_hash(self):
        """Test that the hash method returns a unique hash based on the name."""
        os1 = ImageVersionOS(name="Ubuntu 22.04")
        os2 = ImageVersionOS(name="Ubuntu 22.04")
        os3 = ImageVersionOS(name="Ubuntu 24.04")

        assert hash(os1) == hash(os2)
        assert hash(os1) != hash(os3)

    def test_equality(self):
        """Test that the equality operator compares based on name."""
        os1 = ImageVersionOS(name="Ubuntu 22.04")
        os2 = ImageVersionOS(name="Ubuntu 22.04", primary=True)
        os3 = ImageVersionOS(name="Ubuntu 24.04")

        assert os1 == os2
        assert os1 != os3
        assert os2 != os3


class TestImageVersion:
    def test_name_required(self, caplog):
        """Test that an ImageVersion object requires a name."""
        with pytest.raises(ValidationError, match="Field required"):
            ImageVersion()
        assert "WARNING" not in caplog.text

    def test_name_only(self):
        """Test creating an ImageVersion object with only the name does not raise an exception.

        Test that the default values for subpath, latest, registries, and os are set correctly.
        """
        i = ImageVersion(name="1.0.0")

        assert i.parent is None
        assert i.subpath == "1.0.0"
        assert not i.latest
        assert len(i.all_registries) == 0
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
        assert (
            "No primary OS defined for image version '1.0.0'. At least one OS should be marked as primary for "
            "complete tagging and labeling of images."
        ) not in caplog.text

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


class TestImageVariant:
    def test_name_required(self, caplog):
        """Test that an ImageVariant object requires a name."""
        with pytest.raises(ValidationError, match="Field required"):
            ImageVariant()
        assert "WARNING" not in caplog.text

    def test_valid(self):
        """Test creating a valid ImageVariant object does not raise an exception."""
        i = ImageVariant(name="Variant 1")

        assert i.parent is None
        assert i.name == "Variant 1"
        assert not i.primary
        assert i.extension == "variant1"
        assert i.tagDisplayName == "variant-1"
        assert len(i.tagPatterns) == 0
        assert len(i.options) == 1

    def test_custom_options(self):
        """Test creating an ImageVariant with custom options."""
        custom_options = [{"tool": "goss", "wait": 10, "command": "/bin/bash -c 'my command'"}]
        i = ImageVariant(name="Custom Goss", options=custom_options)

        assert len(i.options) == 1
        assert i.options[0].tool == "goss"
        assert i.options[0].wait == 10
        assert i.options[0].command == "/bin/bash -c 'my command'"

    def test_unknown_options(self):
        """Test creating an ImageVariant with unknown options raises an exception."""
        with pytest.raises(ValidationError):
            ImageVariant(name="Invalid Variant", options=[{"tool": "unknown_tool"}])

    def test_extension_validation(self):
        """Test that the extension field only allows alphanumeric characters, underscores, and hyphens."""
        with pytest.raises(ValidationError):
            ImageVariant(name="Standard", extension="invalid_extension!")

    def test_tag_display_name_validation(self):
        """Test that the tagDisplayName field only allows alphanumeric characters, underscores, hyphens, and periods."""
        with pytest.raises(ValidationError):
            ImageVariant(name="Standard", tagDisplayName="invalid tag name!")

    @staticmethod
    def tool_option_test_params() -> list[ParameterSet]:
        return [
            pytest.param(
                "goss",
                [],
                [],
                {"wait": 0, "command": "sleep infinity"},
                id="defaults",
            ),
            pytest.param(
                "goss",
                [{"tool": "goss", "wait": 5, "command": "command"}],
                [],
                {"wait": 5, "command": "command"},
                id="parent_overrides_defaults",
            ),
            pytest.param(
                "goss",
                [{"tool": "goss", "wait": 5, "command": "command"}],
                [{"tool": "goss", "wait": 10, "command": "other_command"}],
                {"wait": 10, "command": "other_command"},
                id="variant_overrides_parent",
            ),
            pytest.param(
                "goss",
                [{"tool": "goss", "wait": 5, "command": "command"}],
                [{"tool": "goss", "wait": 0, "command": "sleep infinity"}],
                {"wait": 0, "command": "sleep infinity"},
                id="variant_explicit_default",
            ),
        ]

    @pytest.mark.parametrize("tool_name,parent_tool_options,tool_options,expected_values", tool_option_test_params())
    def test_get_tool_option(self, tool_name, parent_tool_options, tool_options, expected_values):
        """Test that get_tool_option returns the correct tool options."""
        parent_image = MagicMock(spec=Image)
        parent_image.options = parent_tool_options
        parent_image.get_tool_option.return_value = (
            GossOptions(**parent_tool_options[0]) if parent_tool_options else None
        )

        # Must be done this way as options will not appear in model_fields_set if not set during instantiation.
        if tool_options:
            i = ImageVariant(name="test", parent=parent_image, options=tool_options)
        else:
            i = ImageVariant(name="test", parent=parent_image)

        options = i.get_tool_option(tool_name)
        for key, value in expected_values.items():
            assert getattr(options, key) == value


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
        assert len(i.variants) == 2
        for variant in i.variants:
            assert variant.parent is i
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

    def test_create_version_files(self, basic_tmpcontext):
        """Test that create_version_files creates the correct directory structure."""
        mock_parent = MagicMock(spec=BakeryConfigDocument)
        mock_parent.path = basic_tmpcontext
        mock_parent.registries = [Registry(host="docker.io", namespace="posit")]

        i = Image(name="test-image", versions=[{"name": "1.0.0"}], parent=mock_parent)
        new_version = ImageVersion(
            parent=i,
            name="2.0.0",
            subpath="2.0",
            os=[{"name": "Ubuntu 22.04", "primary": True}],
        )

        Image.create_version_files(new_version, i.variants)

        expected_path = basic_tmpcontext / "test-image" / "2.0"
        assert expected_path.exists() and expected_path.is_dir()
        assert (expected_path / "Containerfile.ubuntu2204.min").is_file()
        assert (expected_path / "Containerfile.ubuntu2204.std").is_file()
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
