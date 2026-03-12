import datetime
import re
from unittest.mock import patch, MagicMock

import pytest
import python_on_whales

from posit_bakery.config.dependencies import PythonDependencyVersions, RDependencyVersions
from posit_bakery.config.tag import default_tag_patterns, TagPatternFilter
from posit_bakery.const import OCI_LABEL_PREFIX, POSIT_LABEL_PREFIX
from posit_bakery.image.image_metadata import BuildMetadata
from posit_bakery.image.image_target import ImageTarget, ImageTargetSettings, Tag
from posit_bakery.settings import SETTINGS
from test.helpers import remove_images, SUCCESS_SUITES

pytestmark = [
    pytest.mark.unit,
]


class TestTag:
    @pytest.mark.parametrize(
        "ref,expected_registry,expected_repo,expected_suffix,expected_digest",
        [
            # Standard registry with digest
            (
                "ghcr.io/posit-dev/test/tmp@sha256:abc123",
                "ghcr.io",
                "posit-dev/test/tmp",
                None,
                "sha256:abc123",
            ),
            # Standard registry with tag
            (
                "ghcr.io/posit-dev/test:latest",
                "ghcr.io",
                "posit-dev/test",
                "latest",
                None,
            ),
            # Registry with port
            (
                "localhost:5000/repo/image:tag",
                "localhost:5000",
                "repo/image",
                "tag",
                None,
            ),
            # Docker Hub implicit registry
            (
                "library/ubuntu:22.04",
                "docker.io",
                "library/ubuntu",
                "22.04",
                None,
            ),
            # Simple image name (Docker Hub)
            (
                "ubuntu:22.04",
                "docker.io",
                "ubuntu",
                "22.04",
                None,
            ),
            # Azure Container Registry
            (
                "myregistry.azurecr.io/repo/image@sha256:def456",
                "myregistry.azurecr.io",
                "repo/image",
                None,
                "sha256:def456",
            ),
            # No tag or digest
            (
                "ghcr.io/posit-dev/image",
                "ghcr.io",
                "posit-dev/image",
                None,
                None,
            ),
        ],
    )
    def test_tag_from_string(self, ref, expected_registry, expected_repo, expected_suffix, expected_digest):
        """Test parsing various image reference formats."""
        tag = Tag.from_string(ref)
        assert tag.registry.base_url == expected_registry
        assert tag.repository == expected_repo
        assert tag.suffix == expected_suffix
        assert tag.digest == expected_digest


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
        assert all(tag in target.tags.as_strings() for tag in expected_tags)

    @pytest.mark.parametrize(
        "is_matrix,dependencies,values,expected_args",
        [
            pytest.param(
                False,
                [],
                {},
                {},
                id="not-matrix-no-deps-no-values",
            ),
            pytest.param(
                True,
                [],
                {},
                {},
                id="matrix-no-deps-no-values",
            ),
            pytest.param(
                False,
                [
                    PythonDependencyVersions(dependency="python", versions=["3.13.7"]),
                    RDependencyVersions(dependency="R", versions=["4.3.3"]),
                ],
                {},
                {},
                id="no-matrix-deps-no-values",
            ),
            pytest.param(
                True,
                [
                    PythonDependencyVersions(dependency="python", versions=["3.13.7"]),
                    RDependencyVersions(dependency="R", versions=["4.3.3"]),
                ],
                {},
                {"PYTHON_VERSION": "3.13.7", "R_VERSION": "4.3.3"},
                id="matrix-deps-no-values",
            ),
            pytest.param(
                False,
                [],
                {"golang_version": "1.25.2"},
                {},
                id="no-matrix-no-deps-values",
            ),
            pytest.param(
                True,
                [],
                {"golang_version": "1.25.2"},
                {"GOLANG_VERSION": "1.25.2"},
                id="matrix-no-deps-values",
            ),
            pytest.param(
                False,
                [
                    PythonDependencyVersions(dependency="python", versions=["3.13.7"]),
                    RDependencyVersions(dependency="R", versions=["4.3.3"]),
                ],
                {"golang_version": "1.25.2"},
                {},
                id="no-matrix-deps-values",
            ),
            pytest.param(
                True,
                [
                    PythonDependencyVersions(dependency="python", versions=["3.13.7"]),
                    RDependencyVersions(dependency="R", versions=["4.3.3"]),
                ],
                {"golang_version": "1.25.2"},
                {"PYTHON_VERSION": "3.13.7", "R_VERSION": "4.3.3", "GOLANG_VERSION": "1.25.2"},
                id="matrix-deps-values",
            ),
        ],
    )
    def test_build_args(self, get_config_obj, is_matrix, dependencies, values, expected_args):
        """Test creating a new ImageTarget object."""
        basic_config_obj = get_config_obj("basic")
        image = basic_config_obj.model.get_image("test-image")
        version = image.get_version("1.0.0")
        version.isMatrixVersion = is_matrix
        version.dependencies = dependencies
        version.values = values
        variant = image.get_variant("Standard")
        os = version.os[0]

        target = ImageTarget.new_image_target(
            repository=basic_config_obj.model.repository,
            image_version=version,
            image_variant=variant,
            image_os=os,
        )

        assert target.build_args == expected_args

    @pytest.mark.parametrize(
        "target_name,expected_ref",
        [
            (
                "basic_standard_image_target",
                "docker.io/posit/test-image:1.0.0",
            ),
            (
                "basic_minimal_image_target",
                "docker.io/posit/test-image:1.0.0-min",
            ),
        ],
    )
    def test_ref(self, request, target_name, expected_ref):
        """Test ref returns first tag when no build metadata exists."""
        target = request.getfixturevalue(target_name)
        assert target.ref().endswith(expected_ref)

    def test_ref_from_metadata(self, basic_standard_image_target):
        """Test ref returns image_ref from metadata when platform matches."""
        mock_metadata = MagicMock(spec=BuildMetadata)
        mock_metadata.platform = f"linux/{SETTINGS.architecture}"
        mock_metadata.image_ref = "test-image@sha256:1234567890abcdef"
        basic_standard_image_target.build_metadata = [mock_metadata]
        assert basic_standard_image_target.ref() == "test-image@sha256:1234567890abcdef"

    def test_ref_from_metadata_platform_mismatch(self, basic_standard_image_target):
        """Test ref falls back to first tag when metadata exists but platform doesn't match."""
        mock_metadata = MagicMock(spec=BuildMetadata)
        mock_metadata.platform = "linux/arm64"  # Different from default
        mock_metadata.image_ref = "test-image@sha256:arm64digest"
        mock_metadata.created_at = datetime.datetime.now()
        basic_standard_image_target.build_metadata = [mock_metadata]
        # Should fall back to first tag since platform doesn't match
        assert basic_standard_image_target.ref().endswith("docker.io/posit/test-image:1.0.0")

    def test_ref_from_metadata_explicit_platform(self, basic_standard_image_target):
        """Test ref returns correct image_ref when explicit platform is specified."""
        mock_metadata_amd64 = MagicMock(spec=BuildMetadata)
        mock_metadata_amd64.platform = "linux/amd64"
        mock_metadata_amd64.image_ref = "test-image@sha256:amd64digest"
        mock_metadata_amd64.created_at = datetime.datetime.now()

        mock_metadata_arm64 = MagicMock(spec=BuildMetadata)
        mock_metadata_arm64.platform = "linux/arm64"
        mock_metadata_arm64.image_ref = "test-image@sha256:arm64digest"
        mock_metadata_arm64.created_at = datetime.datetime.now()

        basic_standard_image_target.build_metadata = [mock_metadata_amd64, mock_metadata_arm64]

        assert basic_standard_image_target.ref(platform="linux/amd64") == "test-image@sha256:amd64digest"
        assert basic_standard_image_target.ref(platform="linux/arm64") == "test-image@sha256:arm64digest"

    def test_ref_from_metadata_uses_most_recent(self, basic_standard_image_target):
        """Test ref returns image_ref from most recent metadata when multiple exist for same platform."""
        older_time = datetime.datetime(2024, 1, 1, 12, 0, 0)
        newer_time = datetime.datetime(2024, 1, 2, 12, 0, 0)

        mock_metadata_old = MagicMock(spec=BuildMetadata)
        mock_metadata_old.platform = f"linux/{SETTINGS.architecture}"
        mock_metadata_old.image_ref = "test-image@sha256:olddigest"
        mock_metadata_old.created_at = older_time

        mock_metadata_new = MagicMock(spec=BuildMetadata)
        mock_metadata_new.platform = f"linux/{SETTINGS.architecture}"
        mock_metadata_new.image_ref = "test-image@sha256:newdigest"
        mock_metadata_new.created_at = newer_time

        # Add in reverse order to verify sorting
        basic_standard_image_target.build_metadata = [mock_metadata_old, mock_metadata_new]

        assert basic_standard_image_target.ref() == "test-image@sha256:newdigest"

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

    def test_temp_name(self, basic_standard_image_target):
        """Test the temp_name property of an ImageTarget."""
        assert basic_standard_image_target.temp_name is None
        basic_standard_image_target.settings = ImageTargetSettings(temp_registry="ghcr.io/posit-dev")
        assert basic_standard_image_target.temp_name == "ghcr.io/posit-dev/test-image/tmp"

    @pytest.mark.build
    def test_build_args(self, basic_standard_image_target):
        """Test the build property of an ImageTarget."""
        expected_build_args = {
            "context_path": basic_standard_image_target.context.base_path,
            "file": basic_standard_image_target.containerfile,
            "build_args": {},
            "tags": basic_standard_image_target.tags.as_strings(),
            "labels": basic_standard_image_target.labels,
            "load": True,
            "push": False,
            "pull": False,
            "output": {},
            "cache": True,
            "cache_from": None,
            "cache_to": None,
            "metadata_file": None,
            "platforms": ["linux/amd64"],
        }

        with patch("python_on_whales.docker.build") as mock_build:
            basic_standard_image_target.build()

        mock_build.assert_called_once_with(**expected_build_args)

    @pytest.mark.build
    def test_build_args_with_build_args(self, basic_standard_image_target):
        """Test the build property of an ImageTarget when build args are applicable."""
        basic_standard_image_target.image_version.isMatrixVersion = True
        basic_standard_image_target.image_version.dependencies = [
            PythonDependencyVersions(dependency="python", versions=["3.13.7"]),
            RDependencyVersions(dependency="R", versions=["4.3.3"]),
        ]

        expected_build_args = {
            "context_path": basic_standard_image_target.context.base_path,
            "file": basic_standard_image_target.containerfile,
            "build_args": {"PYTHON_VERSION": "3.13.7", "R_VERSION": "4.3.3"},
            "tags": basic_standard_image_target.tags.as_strings(),
            "labels": basic_standard_image_target.labels,
            "load": True,
            "push": False,
            "pull": False,
            "output": {},
            "cache": True,
            "cache_from": None,
            "cache_to": None,
            "metadata_file": None,
            "platforms": ["linux/amd64"],
        }

        with patch("python_on_whales.docker.build") as mock_build:
            basic_standard_image_target.build()

        mock_build.assert_called_once_with(**expected_build_args)

    @pytest.mark.build
    def test_build_args_cache_registry(self, basic_standard_image_target):
        """Test the build property of an ImageTarget."""
        basic_standard_image_target.settings = ImageTargetSettings(cache_registry="ghcr.io/posit-dev")
        cache_name = basic_standard_image_target.cache_name(platform="linux/amd64")
        expected_build_args = {
            "context_path": basic_standard_image_target.context.base_path,
            "file": basic_standard_image_target.containerfile,
            "build_args": {},
            "tags": basic_standard_image_target.tags.as_strings(),
            "labels": basic_standard_image_target.labels,
            "load": True,
            "push": False,
            "pull": False,
            "output": {},
            "cache": True,
            "cache_from": f"type=registry,ref={cache_name}",
            "cache_to": f"type=registry,ref={cache_name},mode=max",
            "metadata_file": None,
            "platforms": ["linux/amd64"],
        }

        with patch("python_on_whales.docker.build") as mock_build:
            basic_standard_image_target.build()

        mock_build.assert_called_once_with(**expected_build_args)

    @pytest.mark.build
    def test_build_args_temp_registry(self, basic_standard_image_target):
        """Test the build property of an ImageTarget."""
        basic_standard_image_target.settings = ImageTargetSettings(temp_registry="ghcr.io/posit-dev")
        expected_build_args = {
            "context_path": basic_standard_image_target.context.base_path,
            "file": basic_standard_image_target.containerfile,
            "build_args": {},
            "tags": [basic_standard_image_target.temp_name],
            "labels": basic_standard_image_target.labels,
            "load": True,
            "push": False,
            "pull": False,
            "output": {"type": "image", "push-by-digest": True, "name-canonical": True, "push": True},
            "cache": True,
            "cache_from": None,
            "cache_to": None,
            "metadata_file": None,
            "platforms": ["linux/amd64"],
        }

        with patch("python_on_whales.docker.build") as mock_build:
            basic_standard_image_target.build(push=True)

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
            for tag in target.tags.as_strings():
                assert python_on_whales.docker.image.exists(tag)
                for key, value in target.labels.items():
                    meta = python_on_whales.docker.image.inspect(tag)
                    assert key in meta.config.labels
                    assert value == meta.config.labels[key]

            remove_images(target)

    @pytest.mark.build
    @pytest.mark.slow
    @pytest.mark.xdist_group(name="build")
    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_build_metadata_file(self, suite, get_targets):
        """Test the build property of an ImageTarget."""
        image_targets = get_targets(suite)
        for target in image_targets:
            target.build(metadata_file=True)
            for tag in target.tags.as_strings():
                assert python_on_whales.docker.image.exists(tag)
                for key, value in target.labels.items():
                    meta = python_on_whales.docker.image.inspect(tag)
                    assert key in meta.config.labels
                    assert value == meta.config.labels[key]

            metadata_file = SETTINGS.temporary_storage / f"{target.uid}.json"
            assert metadata_file.is_file()
            with open(metadata_file) as f:
                data = f.read()
            metadata = BuildMetadata.model_validate_json(data)
            metadata.image_tags.sort()
            assert metadata.image_tags == target.tags.as_strings()

            remove_images(target)

    def test_get_merge_sources_multiple_platforms(self, basic_standard_image_target):
        """Test get_merge_sources returns most recent source for each platform."""
        basic_standard_image_target.build_metadata = [
            MagicMock(spec=BuildMetadata),
            MagicMock(spec=BuildMetadata),
        ]
        basic_standard_image_target.build_metadata[0].created_at = datetime.datetime.now()
        basic_standard_image_target.build_metadata[1].created_at = datetime.datetime.now()
        basic_standard_image_target.build_metadata[0].platform = "linux/amd64"
        basic_standard_image_target.build_metadata[1].platform = "linux/arm64"
        basic_standard_image_target.build_metadata[0].image_ref = "image1@sha256:amd64digest"
        basic_standard_image_target.build_metadata[1].image_ref = "image2@sha256:arm64digest"

        sources = basic_standard_image_target.get_merge_sources()

        assert len(sources) == 2
        assert "image1@sha256:amd64digest" in sources
        assert "image2@sha256:arm64digest" in sources

    def test_get_merge_sources_duplicate_platforms_uses_most_recent(self, basic_standard_image_target):
        """Test get_merge_sources returns only most recent source when platform appears multiple times."""
        older_time = datetime.datetime(2024, 1, 1, 12, 0, 0)
        newer_time = datetime.datetime(2024, 1, 2, 12, 0, 0)

        basic_standard_image_target.build_metadata = [
            MagicMock(spec=BuildMetadata),
            MagicMock(spec=BuildMetadata),
            MagicMock(spec=BuildMetadata),
        ]
        # Older amd64 build
        basic_standard_image_target.build_metadata[0].created_at = older_time
        basic_standard_image_target.build_metadata[0].platform = "linux/amd64"
        basic_standard_image_target.build_metadata[0].image_ref = "old-amd64@sha256:old"
        # Newer amd64 build
        basic_standard_image_target.build_metadata[1].created_at = newer_time
        basic_standard_image_target.build_metadata[1].platform = "linux/amd64"
        basic_standard_image_target.build_metadata[1].image_ref = "new-amd64@sha256:new"
        # arm64 build
        basic_standard_image_target.build_metadata[2].created_at = older_time
        basic_standard_image_target.build_metadata[2].platform = "linux/arm64"
        basic_standard_image_target.build_metadata[2].image_ref = "arm64@sha256:arm"

        sources = basic_standard_image_target.get_merge_sources()

        assert len(sources) == 2
        assert "new-amd64@sha256:new" in sources
        assert "old-amd64@sha256:old" not in sources
        assert "arm64@sha256:arm" in sources

    def test_get_merge_sources_empty_metadata_no_sources(self, basic_standard_image_target):
        """Test get_merge_source with empty metadata returns no sources."""
        basic_standard_image_target.build_metadata = []

        assert len(basic_standard_image_target.get_merge_sources()) == 0

    def test_get_merge_sources_single_platform(self, basic_standard_image_target):
        """Test get_merge_sources works with single platform."""
        basic_standard_image_target.build_metadata = [
            MagicMock(spec=BuildMetadata),
        ]
        basic_standard_image_target.build_metadata[0].created_at = datetime.datetime.now()
        basic_standard_image_target.build_metadata[0].platform = "linux/amd64"
        basic_standard_image_target.build_metadata[0].image_ref = "image@sha256:digest"

        sources = basic_standard_image_target.get_merge_sources()

        assert sources == ["image@sha256:digest"]
