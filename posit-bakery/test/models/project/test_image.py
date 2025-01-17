from pathlib import Path
from unittest.mock import patch

import pytest

from posit_bakery.error import BakeryFileNotFoundError
from posit_bakery.models import Image, ManifestDocument
from posit_bakery.models.manifest import find_os
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.target import ManifestTarget
from posit_bakery.models.project.image import ImageVariant


BUILD_LATEST: ManifestBuild = ManifestBuild(
    os=["Ubuntu 24.04"],
    latest=True,
)
BUILD_SIMPLE: ManifestBuild = ManifestBuild(
    os=["Ubuntu 24.04"],
)
BUILD_MULTI_OS: ManifestBuild = ManifestBuild(
    os=[
        "Ubuntu 24.04",
        "Ubuntu 22.04",
        "Rocky Linux 9",
    ]
)


TARGET_MIN: ManifestTarget = ManifestTarget()
TARGET_STD: ManifestTarget = ManifestTarget()
TARGET_COMPLEX: ManifestTarget = ManifestTarget()
TARGET_PREVIEW: ManifestTarget = ManifestTarget()


@pytest.fixture(scope="module")
def manifest_simple():
    return ManifestDocument(
        image_name="simple-image",
        build={"simple": BUILD_SIMPLE},
        target={"min": TARGET_MIN},
    )


@pytest.fixture(scope="module")
def manifest_latest():
    return ManifestDocument(
        image_name="latest-image",
        build={"latest": BUILD_LATEST},
        target={"min": TARGET_MIN},
    )


@pytest.fixture(scope="module")
def manifest_multi_os():
    return ManifestDocument(
        image_name="multi-os-image",
        build={"multi-os": BUILD_MULTI_OS},
        target={"min": TARGET_MIN, "std": TARGET_STD},
    )


@pytest.fixture(scope="module")
def manifest_matrix():
    return ManifestDocument(
        image_name="matrix-image",
        build={
            "simple": BUILD_SIMPLE,  # 4 variants
            "latest": BUILD_LATEST,  # 4 variants
            "complex": BUILD_MULTI_OS,  # 12 variants
        },
        target={
            "min": TARGET_MIN,
            "std": TARGET_STD,
            "complex": TARGET_COMPLEX,
            "preview": TARGET_COMPLEX,
        },
    )


# TODO: Figure out how to patch Path.is_file for this class
@pytest.mark.image
class TestImageMatrix:
    context: Path = Path("fancy-image")

    def test_load_simple(self, manifest_simple):
        """Test creating an image with a single build and target"""
        with patch("pathlib.Path.is_file", side_effect=[True]):
            image: Image = Image.load(self.context, manifest_simple)

        assert image.name == "simple-image"
        assert image.context == self.context

        assert len(image.versions) == 1
        assert image.versions[0].version == "simple"

        assert len(image.versions[0].variants) == 1
        assert image.versions[0].variants[0].latest is False

    def test_load_latest(self, manifest_latest):
        """Test creating an image with a single build and target"""
        with patch("pathlib.Path.is_file", side_effect=[True]):
            image: Image = Image.load(self.context, manifest_latest)

        assert image.name == "latest-image"
        assert image.context == self.context

        assert len(image.versions) == 1
        assert image.versions[0].version == "latest"

        assert len(image.versions[0].variants) == 1
        assert image.versions[0].variants[0].latest is True

    def test_load_multi_os(self, manifest_multi_os):
        """Test creating an image with multiple OS and default targets"""
        with patch("pathlib.Path.is_file", side_effect=[True]):
            image: Image = Image.load(self.context, manifest_multi_os)

        assert image.name == "multi-os-image"
        assert image.context == self.context

        assert len(image.versions) == 1
        assert image.versions[0].version == "multi-os"
        assert len(image.versions[0].variants) == 6
        assert len(image.targets) == 6

    def test_load_matrix(self, manifest_matrix):
        """Test creating an image with multiple builds and targets"""
        with patch("pathlib.Path.is_file", side_effect=[True]):
            image: Image = Image.load(self.context, manifest_matrix)

        assert image.name == "matrix-image"
        assert image.context == self.context

        assert len(image.versions) == 3
        assert len(image.targets) == 20


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

        with patch("pathlib.Path.is_file", side_effect=[False, False, False]):
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

        with patch("pathlib.Path.is_file", side_effect=[True]):
            variant: ImageVariant = ImageVariant.load(self.context, latest, _os, target)

        assert variant.latest is latest
        assert variant.os == _os
        assert variant.target == target
        assert variant.containerfile == filepath
