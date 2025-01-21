import pytest

from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.document import ManifestDocument
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
        build={"v0.1.0": BUILD_SIMPLE},
        target={"min": TARGET_MIN},
    )


@pytest.fixture
def manifest_latest():
    return ManifestDocument(
        image_name="latest-image",
        build={"v1.2.3": BUILD_LATEST},
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
            "v0.1.0": BUILD_SIMPLE,  # 4 variants
            "v1.2.3": BUILD_LATEST,  # 4 variants
            "v0.2.5-147f295": BUILD_MULTI_OS,  # 12 variants
        },
        target={
            "min": TARGET_MIN,
            "std": TARGET_STD,
            "complex": TARGET_COMPLEX,
            "preview": TARGET_COMPLEX,
        },
    )
