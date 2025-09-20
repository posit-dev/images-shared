import re
from unittest.mock import patch

import pytest
import python_on_whales

from posit_bakery.config.tag import default_tag_patterns, TagPatternFilter
from posit_bakery.const import OCI_LABEL_PREFIX, POSIT_LABEL_PREFIX
from posit_bakery.image.image_target import ImageTarget
from test.helpers import remove_images, SUCCESS_SUITES

pytestmark = [
    pytest.mark.unit,
]


class TestImageTarget:
    def test_new_image_target(self, get_config_obj):
        """Test creating a new ImageTarget object."""
        basic_config_obj = get_config_obj("basic")
        image = basic_config_obj.model.get_image("test-image")
        version = image.get_version("1.0.0")
        variant = image.get_variant("Standard")
        os = version.os[0]

        target = ImageTarget.new_image_target(
            repository=basic_config_obj.model.repository,
            image_version=version,
            image_variant=variant,
            image_os=os,
        )

        assert target.context.base_path == basic_config_obj.model.path
        assert target.context.image_path == image.path
        assert target.context.version_path == version.path
        assert target.repository == basic_config_obj.model.repository
        assert target.image_version == version
        assert target.image_variant == variant
        assert target.image_os == os
        assert len(target.tag_patterns) == 8

    def test_str(self, get_config_obj, basic_standard_image_target):
        """Test the string representation of an ImageTarget."""
        basic_config_obj = get_config_obj("basic")
        image = basic_config_obj.model.get_image("test-image")
        version = image.get_version("1.0.0")
        variant = image.get_variant("Standard")
        os = version.os[0]

        expected_str = (
            f"ImageTarget(image='{image.name}', version='{version.name}', variant='{variant.name}', os='{os.name}')"
        )
        assert str(basic_standard_image_target) == expected_str

    def test_uid(self, get_config_obj, basic_standard_image_target):
        """Test the UID of an ImageTarget."""
        basic_config_obj = get_config_obj("basic")
        image = basic_config_obj.model.get_image("test-image")
        version = image.get_version("1.0.0")
        variant = image.get_variant("Standard")
        os = version.os[0]

        expected_uid = re.sub(r"[ .+/]", "-", f"{image.name}-{version.name}-{variant.name}-{os.name}").lower()
        assert basic_standard_image_target.uid == expected_uid

    def test_image_name(self, basic_standard_image_target):
        assert basic_standard_image_target.image_name == "test-image"

    def test_is_latest(self, basic_standard_image_target):
        """Test the is_latest property of an ImageTarget."""
        assert basic_standard_image_target.is_latest

        basic_standard_image_target.image_version.latest = False

        assert not basic_standard_image_target.is_latest

    def test_is_primary_os(self, basic_standard_image_target):
        """Test the is_primary_os property of an ImageTarget."""
        assert basic_standard_image_target.is_primary_os

        # Change the primary OS and check again
        basic_standard_image_target.image_version.os[0].primary = False
        assert not basic_standard_image_target.is_primary_os

    def test_is_primary_os_no_os(self, basic_standard_image_target):
        """Test the is_primary_os property of an ImageTarget."""
        basic_standard_image_target.image_os = None
        assert basic_standard_image_target.is_primary_os

    def test_is_primary_variant(self, basic_standard_image_target):
        """Test the is_primary_variant property of an ImageTarget."""
        assert basic_standard_image_target.is_primary_variant

        # Change the primary variant and check again
        basic_standard_image_target.image_variant.primary = False
        assert not basic_standard_image_target.is_primary_variant

    def test_is_primary_variant_no_variant(self, basic_standard_image_target):
        """Test the is_primary_variant property of an ImageTarget."""
        basic_standard_image_target.image_variant = None
        assert basic_standard_image_target.is_primary_variant

    def test_containerfile(self, get_config_obj, basic_standard_image_target):
        """Test the containerfile property of an ImageTarget."""
        basic_config_obj = get_config_obj("basic")
        expected_path = (
            basic_standard_image_target.image_version.parent.path
            / basic_standard_image_target.image_version.path
            / f"Containerfile.{basic_standard_image_target.image_os.extension}."
            f"{basic_standard_image_target.image_variant.extension}"
        ).relative_to(basic_config_obj.model.path)
        assert basic_standard_image_target.containerfile == expected_path

    def test_containerfile_no_variant(self, get_config_obj, basic_standard_image_target):
        """Test the containerfile property of an ImageTarget without a variant."""
        basic_config_obj = get_config_obj("basic")
        basic_standard_image_target.image_variant = None
        expected_path = (
            basic_standard_image_target.image_version.parent.path
            / basic_standard_image_target.image_version.path
            / f"Containerfile.{basic_standard_image_target.image_os.extension}"
        ).relative_to(basic_config_obj.model.path)
        assert basic_standard_image_target.containerfile == expected_path

    def test_containerfile_no_os(self, get_config_obj, basic_standard_image_target):
        """Test the containerfile property of an ImageTarget without an OS."""
        basic_config_obj = get_config_obj("basic")
        basic_standard_image_target.image_os = None
        expected_path = (
            basic_standard_image_target.image_version.parent.path
            / basic_standard_image_target.image_version.path
            / f"Containerfile.{basic_standard_image_target.image_variant.extension}"
        ).relative_to(basic_config_obj.model.path)
        assert basic_standard_image_target.containerfile == expected_path

    def test_containerfile_no_variant_no_os(self, get_config_obj, basic_standard_image_target):
        """Test the containerfile property of an ImageTarget without an OS."""
        basic_config_obj = get_config_obj("basic")
        basic_standard_image_target.image_variant = None
        basic_standard_image_target.image_os = None
        expected_path = (
            basic_standard_image_target.image_version.parent.path
            / basic_standard_image_target.image_version.path
            / f"Containerfile"
        ).relative_to(basic_config_obj.model.path)
        assert basic_standard_image_target.containerfile == expected_path

    def test_tag_template_values(self, basic_standard_image_target):
        """Test the tag_template_values property of an ImageTarget."""
        # Test standard behavior
        expected_values = {
            "Name": basic_standard_image_target.image_name,
            "Version": basic_standard_image_target.image_version.name,
            "Variant": basic_standard_image_target.image_variant.tagDisplayName,
            "OS": basic_standard_image_target.image_os.tagDisplayName,
        }
        assert basic_standard_image_target.tag_template_values == expected_values

        # Check variant and OS are set to empty strings when none
        expected_values = {
            "Name": basic_standard_image_target.image_name,
            "Version": basic_standard_image_target.image_version.name,
            "Variant": "",
            "OS": "",
        }
        basic_standard_image_target.image_variant = None
        basic_standard_image_target.image_os = None
        assert basic_standard_image_target.tag_template_values == expected_values

    def test_tag_patterns_deduplication(self, get_config_obj):
        """Test the deduplicate_tag_patterns method of an ImageTarget."""
        basic_config_obj = get_config_obj("basic")
        image = basic_config_obj.model.get_image("test-image")
        version = image.get_version("1.0.0")
        variant = image.get_variant("Standard")
        # Duplicate tag patterns by adding some default patterns that will also be present in Image
        variant.tagPatterns = default_tag_patterns()[:2]
        os = version.os[0]

        target = ImageTarget.new_image_target(
            repository=basic_config_obj.model.repository,
            image_version=version,
            image_variant=variant,
            image_os=os,
        )
        # Check that the tag patterns are deduplicated to 8, the default tag patterns length
        assert len(target.tag_patterns) == 8

    def test_tag_patterns_filtering(self, get_config_obj):
        """Test the filter_tag_patterns method of an ImageTarget."""
        basic_config_obj = get_config_obj("basic")
        # Test latest, primary variant, and primary OS
        image = basic_config_obj.model.get_image("test-image")
        version = image.get_version("1.0.0")
        variant = image.get_variant("Standard")
        os = version.os[0]

        target = ImageTarget.new_image_target(
            repository=basic_config_obj.model.repository,
            image_version=version,
            image_variant=variant,
            image_os=os,
        )
        assert len(target.tag_patterns) == 8

        # Test primary variant and primary OS, but not latest
        version.latest = False

        target = ImageTarget.new_image_target(
            repository=basic_config_obj.model.repository,
            image_version=version,
            image_variant=variant,
            image_os=os,
        )
        assert len(target.tag_patterns) == 4
        assert not any(TagPatternFilter.LATEST in pattern.only for pattern in target.tag_patterns)

        # Test latest and primary OS, but not primary variant
        version.latest = True
        variant.primary = False

        target = ImageTarget.new_image_target(
            repository=basic_config_obj.model.repository,
            image_version=version,
            image_variant=variant,
            image_os=os,
        )
        assert len(target.tag_patterns) == 4
        assert not any(TagPatternFilter.PRIMARY_VARIANT in pattern.only for pattern in target.tag_patterns)

        # Test latest and primary variant, but not primary OS
        variant.primary = True
        os.primary = False

        target = ImageTarget.new_image_target(
            repository=basic_config_obj.model.repository,
            image_version=version,
            image_variant=variant,
            image_os=os,
        )
        assert len(target.tag_patterns) == 4
        assert not any(TagPatternFilter.PRIMARY_OS in pattern.only for pattern in target.tag_patterns)

    @pytest.mark.parametrize(
        "target_name,expected_tag_suffixes",
        [
            (
                "basic_standard_image_target",
                [
                    "1.0.0-ubuntu-22.04-std",
                    "1.0.0-std",
                    "1.0.0-ubuntu-22.04",
                    "1.0.0",
                    "ubuntu-22.04-std",
                    "ubuntu-22.04",
                    "std",
                    "latest",
                ],
            ),
            (
                "basic_minimal_image_target",
                [
                    "1.0.0-ubuntu-22.04-min",
                    "1.0.0-min",
                    "ubuntu-22.04-min",
                    "min",
                ],
            ),
        ],
    )
    def test_tag_suffixes(self, request, target_name, expected_tag_suffixes):
        """Test the tag_suffixes property of an ImageTarget."""
        target = request.getfixturevalue(target_name)

        assert len(expected_tag_suffixes) == len(target.tag_suffixes)
        assert all(tag_suffix in target.tag_suffixes for tag_suffix in expected_tag_suffixes)

    @pytest.mark.parametrize(
        "target_name,expected_tag_suffixes",
        [
            (
                "basic_standard_image_target",
                [
                    "1.0.0-ubuntu-22.04-std",
                    "1.0.0-std",
                    "1.0.0-ubuntu-22.04",
                    "1.0.0",
                    "ubuntu-22.04-std",
                    "ubuntu-22.04",
                    "std",
                    "latest",
                ],
            ),
            (
                "basic_minimal_image_target",
                [
                    "1.0.0-ubuntu-22.04-min",
                    "1.0.0-min",
                    "ubuntu-22.04-min",
                    "min",
                ],
            ),
        ],
    )
    def test_tags(self, request, target_name, expected_tag_suffixes, get_config_obj):
        """Test the tag_suffixes property of an ImageTarget."""
        target = request.getfixturevalue(target_name)
        basic_config_obj = get_config_obj("basic")
        registry_urls = [u.base_url for u in basic_config_obj.model.registries]
        expected_tags = [
            f"{url}/{target.image_name}:{suffix}" for url in registry_urls for suffix in expected_tag_suffixes
        ]

        assert len(expected_tags) == len(target.tags)
        assert all(tag in target.tags for tag in expected_tags)

    def test_labels(self, datetime_now_value, basic_standard_image_target):
        """Test the labels property of an ImageTarget."""
        expected_labels = {
            f"{OCI_LABEL_PREFIX}.created": datetime_now_value.isoformat(),
            f"{OCI_LABEL_PREFIX}.source": "https://github.com/posit-dev/images-shared",
            f"{OCI_LABEL_PREFIX}.title": "Test Image",
            f"{OCI_LABEL_PREFIX}.vendor": "Posit Software, PBC",
            f"{POSIT_LABEL_PREFIX}.maintainer": "Posit Docker Team <docker@posit.co>",
            f"{OCI_LABEL_PREFIX}.authors": "Author 1 <author1@posit.co>, Author 2 <author2@posit.co>",
            f"{POSIT_LABEL_PREFIX}.name": "Test Image",
            f"{POSIT_LABEL_PREFIX}.version": "1.0.0",
            f"{OCI_LABEL_PREFIX}.version": "1.0.0",
            f"{POSIT_LABEL_PREFIX}.variant": "Standard",
            f"{POSIT_LABEL_PREFIX}.os": "Ubuntu 22.04",
        }

        labels = basic_standard_image_target.labels

        for key, value in expected_labels.items():
            assert key in labels
            assert labels[key] == value

    @pytest.mark.build
    def test_build_args(self, basic_standard_image_target):
        """Test the build property of an ImageTarget."""
        expected_build_args = {
            "context_path": basic_standard_image_target.context.base_path,
            "file": basic_standard_image_target.containerfile,
            "tags": basic_standard_image_target.tags,
            "labels": basic_standard_image_target.labels,
            "load": True,
            "push": False,
            "cache": True,
            "platforms": ["linux/amd64"],
        }

        with patch("python_on_whales.docker.build") as mock_build:
            basic_standard_image_target.build()

        mock_build.assert_called_once_with(**expected_build_args)

    @pytest.mark.build
    @pytest.mark.slow
    @pytest.mark.xdist_group(name="build")
    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_build(self, suite, get_targets):
        """Test the build property of an ImageTarget."""
        image_targets = get_targets(suite)
        for target in image_targets:
            target.build()
            for tag in target.tags:
                assert python_on_whales.docker.image.exists(tag)
                for key, value in target.labels.items():
                    meta = python_on_whales.docker.image.inspect(tag)
                    assert key in meta.config.labels
                    assert value == meta.config.labels[key]

            remove_images(target)
