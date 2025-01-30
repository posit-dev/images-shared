from pathlib import Path
from typing import Dict, List
from unittest.mock import patch

import pytest

from posit_bakery.error import BakeryFileNotFoundError
from posit_bakery.models.image.image import Image, ImageMetadata
from posit_bakery.models.image.variant import ImageVariant

from ..fixtures import (
    manifest_simple,
    manifest_latest,
    manifest_multi_os,
    manifest_matrix,
)

pytestmark = [
    pytest.mark.unit,
    pytest.mark.image,
]


@pytest.fixture(autouse=True)
def patch_is_file():
    """Patch pathlib.Path.is_file to always return True

    We use is_file to find the appropriate Containerfile for each ImageVariant
    """
    with patch("pathlib.Path.is_file", return_value=True, autospec=True) as p:
        yield p


@pytest.fixture(autouse=True)
def patch_is_dir():
    """Patch pathlib.Path.is_dir to always return True

    We use is_dir to find the test and dependency directories for goss
    """
    with patch("pathlib.Path.is_dir", return_value=True, autospec=True) as p:
        yield p


# TODO: Figure out how to patch Path.is_file for this class
@pytest.mark.image
class TestImageMatrix:
    context: Path = Path("fancy-image")

    def test_load_simple(self, manifest_simple):
        """Test creating an image with a single build and target"""
        image: Image = Image.load(self.context, manifest_simple)

        assert image.name == "simple-image"
        assert image.context == self.context

        assert len(image.versions) == 1
        assert image.versions[0].version == "0.1.0"

        assert len(image.versions[0].variants) == 1
        assert image.versions[0].variants[0].latest is False

    def test_load_latest(self, manifest_latest):
        """Test creating an image with a single build and target"""
        image: Image = Image.load(self.context, manifest_latest)

        assert image.name == "latest-image"
        assert image.context == self.context

        assert len(image.versions) == 1
        assert image.versions[0].version == "1.2.3"

        assert len(image.versions[0].variants) == 1
        assert image.versions[0].variants[0].latest is True

    def test_load_multi_os(self, manifest_multi_os):
        """Test creating an image with multiple OS and default targets"""
        image: Image = Image.load(self.context, manifest_multi_os)

        assert image.name == "multi-os-image"
        assert image.context == self.context

        assert len(image.versions) == 1
        assert image.versions[0].version == "2.1.5"
        assert len(image.versions[0].variants) == 6
        assert len(image.variants) == 6

    def test_load_matrix(self, manifest_matrix):
        """Test creating an image with multiple builds and targets"""
        image: Image = Image.load(self.context, manifest_matrix)

        assert image.name == "matrix-image"
        assert image.context == self.context

        assert len(image.versions) == 3
        assert len(image.variants) == 20


@pytest.mark.image
class TestImageMetadata:
    context: Path = Path("fancy-image")

    def test_simple_labels(self, manifest_simple):
        """Ensure appropriate labels are being added to the image"""
        image: Image = Image.load(self.context, manifest_simple)

        assert image.name == "simple-image"

        labels: Dict[str, str] = image.versions[0].variants[0].meta.labels

        assert labels.posit_prefix == "co.posit.image"
        assert labels.posit.get("name") == "simple-image"
        assert labels.posit.get("version") == "0.1.0"
        assert labels.posit.get("type") == "min"
        assert labels.posit.get("os") == "Ubuntu 24.04"

        assert labels.oci_prefix == "org.opencontainers.image"
        assert labels.oci.get("title") == "simple-image"

    def test_multi_labels(self, manifest_multi_os):
        """Ensure appropriate labels are being added to all image variants

        This test ensures that labels are being applied to each variant
        and the label objects are unique to each variant
        """
        image: Image = Image.load(self.context, manifest_multi_os)

        assert image.name == "multi-os-image"

        # Ubuntu 24.04
        assert image.versions[0].variants[0].meta.labels.posit.get("os") == "Ubuntu 24.04"
        assert image.versions[0].variants[0].meta.labels.posit.get("type") == "min"
        assert image.versions[0].variants[1].meta.labels.posit.get("os") == "Ubuntu 24.04"
        assert image.versions[0].variants[1].meta.labels.posit.get("type") == "std"
        # Ubuntu 22.04
        assert image.versions[0].variants[2].meta.labels.posit.get("os") == "Ubuntu 22.04"
        assert image.versions[0].variants[2].meta.labels.posit.get("type") == "min"
        assert image.versions[0].variants[3].meta.labels.posit.get("os") == "Ubuntu 22.04"
        assert image.versions[0].variants[3].meta.labels.posit.get("type") == "std"
        # Rocky Linux 9
        assert image.versions[0].variants[4].meta.labels.posit.get("os") == "Rocky Linux 9"
        assert image.versions[0].variants[4].meta.labels.posit.get("type") == "min"
        assert image.versions[0].variants[5].meta.labels.posit.get("os") == "Rocky Linux 9"
        assert image.versions[0].variants[5].meta.labels.posit.get("type") == "std"

    def test_tags_default(self, manifest_simple):
        """Ensure default tags are being added to the image"""
        expected_tags: List[str] = [
            "0.1.0-ubuntu-24.04-min",
            "0.1.0-min",
        ]

        image: Image = Image.load(self.context, manifest_simple)

        tags = image.versions[0].variants[0].meta.tags
        assert len(tags) == len(expected_tags)
        for tag in expected_tags:
            assert tag in tags

    def test_tags_default_latest(self, manifest_latest):
        """Ensure string tags are being added to the image"""
        expected_tags: List[str] = [
            "1.2.3-ubuntu-24.04-min",
            "1.2.3-min",
            "ubuntu-24.04-min",
            "latest",
        ]

        image: Image = Image.load(self.context, manifest_latest)

        tags = image.versions[0].variants[0].meta.tags
        assert len(tags) == len(expected_tags)
        for tag in expected_tags:
            assert tag in tags


@pytest.mark.image
class TestImageVariant:
    context: Path = Path("fancy-image/version")

    def test_find_containerfile_os_invalid(self):
        """Raise an excpetion if the OS is unsupported"""
        with patch("posit_bakery.models.manifest.find_os", side_effect=[None]):
            with pytest.raises(ValueError):
                ImageVariant.find_containerfile(self.context, "unsupported_os", "min")

    def test_find_containerfile_with_os(self):
        """Find the containerfile including the OS if present"""
        _os: str = "Ubuntu 24.04"
        target: str = "min"
        filepath: Path = self.context / "Containerfile.ubuntu2404.min"

        with patch("pathlib.Path.is_file", side_effect=[True]):
            containerfile = ImageVariant.find_containerfile(self.context, _os, target)

        assert containerfile == filepath

    def test_find_containerfile_no_os(self):
        """Find the containerfile with only the target if file with no OS is present"""
        _os: str = "Ubuntu 24.04"
        target: str = "min"
        filepath: Path = self.context / "Containerfile.min"

        with patch("pathlib.Path.is_file", side_effect=[False, True]):
            containerfile = ImageVariant.find_containerfile(self.context, _os, target)

        assert containerfile == filepath

    def test_find_containerfile_missing(self):
        """Raise an exception if no matching containerfile is found"""
        _os: str = "Ubuntu 24.04"
        target: str = "min"

        with patch("pathlib.Path.is_file", side_effect=[False] * 4):
            with pytest.raises(BakeryFileNotFoundError):
                ImageVariant.find_containerfile(self.context, _os, target)

    @pytest.mark.parametrize(
        "latest,_os,target,suffix",
        [
            (True, "Ubuntu 24.04", "min", "ubuntu2404.min"),
            (True, "Ubuntu 24.04", "std", "ubuntu2404.std"),
            (False, "Ubuntu 24.04", "min", "ubuntu2404.min"),
            (False, "Ubuntu 22.04", "std", "ubuntu2204.std"),
            (False, "Rocky Linux 9", "std", "rockylinux9.std"),
        ],
    )
    def test_load(self, latest: bool, _os: str, target: str, suffix: str):
        filepath: Path = self.context / f"Containerfile.{suffix}"

        variant: ImageVariant = ImageVariant.load(
            meta=ImageMetadata(
                name="superlative-image",
                context=self.context,
                version="version",
            ),
            latest=latest,
            _os=_os,
            target=target,
        )

        assert variant.latest is latest
        assert variant.os == _os
        assert variant.target == target
        assert variant.containerfile == filepath
