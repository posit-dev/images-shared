import pytest

from posit_bakery.models.config.document import ConfigDocument
from posit_bakery.models.config.registry import ConfigRegistry
from posit_bakery.models.config.repository import ConfigRepository
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.document import ManifestDocument
from posit_bakery.models.manifest.target import ManifestTarget


REGISTRY_DOCKER: ConfigRegistry = ConfigRegistry(
    host="docker.io",
    namespace="posit",
)
REGISTRY_GHCR: ConfigRegistry = ConfigRegistry(
    host="ghcr.io",
    namespace="posit-dev",
)
REPOSITORY: ConfigRepository = ConfigRepository(
    authors=[
        "author1@sub.tld",
        "Author Name <author.name@example.com>",
    ],
    url="github.com/posit-dev/images-fakename",
    vendor="Posit Software, PBC",
    maintainer="author.name@posit.co",
)

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
def config_simple():
    return ConfigDocument(repository=REPOSITORY, registries=[REGISTRY_DOCKER])


@pytest.fixture
def config_multi_registry():
    return ConfigDocument(repository=REPOSITORY, registries=[REGISTRY_DOCKER, REGISTRY_GHCR])


@pytest.fixture
def manifest_simple():
    return ManifestDocument(
        image_name="simple-image",
        build={"0.1.0": BUILD_SIMPLE},
        target={"min": TARGET_MIN},
    )


@pytest.fixture
def manifest_latest():
    return ManifestDocument(
        image_name="latest-image",
        build={"1.2.3": BUILD_LATEST},
        target={
            "min": TARGET_MIN,
            "std": TARGET_STD,
        },
    )


@pytest.fixture
def manifest_multi_build():
    return ManifestDocument(
        image_name="multi-build-image",
        build={
            "0.1.0": BUILD_SIMPLE,
            "1.2.3": BUILD_LATEST,
        },
        target={
            "min": TARGET_MIN,
            "std": TARGET_STD,
        },
    )


@pytest.fixture
def manifest_multi_os():
    return ManifestDocument(
        image_name="multi-os-image",
        build={"2.1.5": BUILD_MULTI_OS},
        target={"min": TARGET_MIN, "std": TARGET_STD},
    )


@pytest.fixture
def manifest_matrix():
    return ManifestDocument(
        image_name="matrix-image",
        build={
            "0.1.0": BUILD_SIMPLE,  # 4 variants
            "1.2.3": BUILD_LATEST,  # 4 variants
            "2.0.3": BUILD_MULTI_OS,  # 12 variants
        },
        target={
            "min": TARGET_MIN,
            "std": TARGET_STD,
            "complex": TARGET_COMPLEX,
            "preview": TARGET_COMPLEX,
        },
    )
