import pytest

from posit_bakery.models import Image, ManifestDocument
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.target import ManifestTarget


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


@pytest.fixture
def manifest_simple():
    return ManifestDocument(
        image_name="simple-image",
        build={"simple": BUILD_SIMPLE},
        target={"min": TARGET_MIN},
    )


@pytest.fixture
def manifest_latest():
    return ManifestDocument(
        image_name="latest-image",
        build={"latest": BUILD_LATEST},
        target={"min": TARGET_MIN},
    )


@pytest.fixture
def manifest_multi_os():
    return ManifestDocument(
        image_name="multi-os-image",
        build={"multi-os": BUILD_MULTI_OS},
        target={"min": TARGET_MIN, "std": TARGET_STD},
    )


@pytest.fixture
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


@pytest.mark.image
class TestImageMatrix:
    def test_load_simple(self, manifest_simple):
        """Test creating an image with a single build and target"""
        image: Image = Image.load(manifest_simple)

        assert image.name == "simple-image"

        assert len(image.versions) == 1
        assert image.versions[0].version == "simple"

        assert len(image.versions[0].variants) == 1
        assert image.versions[0].variants[0].latest is False

    def test_load_latest(self, manifest_latest):
        """Test creating an image with a single build and target"""
        image: Image = Image.load(manifest_latest)

        assert image.name == "latest-image"

        assert len(image.versions) == 1
        assert image.versions[0].version == "latest"

        assert len(image.versions[0].variants) == 1
        assert image.versions[0].variants[0].latest is True

    def test_load_multi_os(self, manifest_multi_os):
        """Test creating an image with multiple OS and default targets"""
        image: Image = Image.load(manifest_multi_os)

        assert image.name == "multi-os-image"

        assert len(image.versions) == 1
        assert image.versions[0].version == "multi-os"
        assert len(image.versions[0].variants) == 6
        assert len(image.targets) == 6

    def test_load_matrix(self, manifest_matrix):
        """Test creating an image with multiple builds and targets"""
        image: Image = Image.load(manifest_matrix)

        assert image.name == "matrix-image"

        assert len(image.versions) == 3
        assert len(image.targets) == 20
