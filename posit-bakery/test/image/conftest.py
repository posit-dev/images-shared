import pathlib
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockFixture

from posit_bakery.image import ImageTarget
from posit_bakery.image.image_metadata import ImageToolsInspectionMetadata
from posit_bakery.services import RegistryContainer


@pytest.fixture
def image_testdata_path():
    """Return the path to the image testdata directory"""
    return pathlib.Path(__file__).parent / "testdata"


@pytest.fixture
def patch_os_getcwd(mocker: MockFixture):
    """Patch os.getcwd() to return a fixed path."""
    import os

    mock_getcwd = mocker.patch.object(os, "getcwd", return_value="/cwd")
    yield mock_getcwd


@pytest.fixture
def patch_os_chdir(mocker: MockFixture):
    """Patch os.chdir() to prevent changing directories during tests."""
    import os

    mock_chdir = mocker.patch.object(os, "chdir", return_value=None)
    yield mock_chdir


@pytest.fixture
def patch_imagetools_create(mocker: MockFixture):
    """Patch ImageTools.create() to prevent actual image creation during tests."""
    import python_on_whales
    from python_on_whales.components.buildx.imagetools.models import Manifest

    mock_manifest = Manifest.model_validate(
        {
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "schemaVersion": 2,
            "manifests": [
                {
                    "media_type": "application/vnd.oci.image.manifest.v1+json",
                    "size": 2765,
                    "digest": "sha256:fc264c81b11b3310b4231b552d6b38239569b559a983cb2886623b83f5252261",
                    "platform": {"architecture": "amd64", "os": "linux"},
                },
                {
                    "media_type": "application/vnd.oci.image.manifest.v1+json",
                    "size": 2765,
                    "digest": "sha256:0253116f6e3c69e371d32fb857e4f03f2537b28f276847115cce97be744f351d",
                    "platform": {"architecture": "arm64", "os": "linux"},
                },
            ],
        }
    )
    mock_create = mocker.patch.object(
        python_on_whales.docker.buildx.imagetools,
        "create",
        return_value=mock_manifest,
    )
    yield mock_create


@pytest.fixture
def patch_imagetools_inspect(mocker: MockFixture):
    """Patch ImageTools.inspect() to prevent actual inspection during tests."""
    import python_on_whales
    from python_on_whales.components.buildx.imagetools.models import Manifest

    mock_manifest = Manifest.model_validate(
        {
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "schemaVersion": 2,
            "manifests": [
                {
                    "media_type": "application/vnd.oci.image.manifest.v1+json",
                    "size": 2765,
                    "digest": "sha256:fc264c81b11b3310b4231b552d6b38239569b559a983cb2886623b83f5252261",
                    "platform": {"architecture": "amd64", "os": "linux"},
                },
                {
                    "media_type": "application/vnd.oci.image.manifest.v1+json",
                    "size": 2765,
                    "digest": "sha256:0253116f6e3c69e371d32fb857e4f03f2537b28f276847115cce97be744f351d",
                    "platform": {"architecture": "arm64", "os": "linux"},
                },
            ],
        }
    )
    mock_inspect = mocker.patch.object(
        python_on_whales.docker.buildx.imagetools,
        "inspect",
        return_value=mock_manifest,
    )
    yield mock_inspect


@pytest.fixture
def patch_registry_container(mocker: MockFixture):
    """Patch RegistryContainer methods to prevent actual registry interactions during tests."""
    mock_registry = MagicMock(spec=RegistryContainer)
    mock_registry.url = "localhost:5000"

    mock_context_manager = MagicMock(spec=RegistryContainer)
    mock_context_manager.__enter__.return_value = mock_registry

    mock_registry_container = mocker.patch(
        "posit_bakery.image.image_target.RegistryContainer",
        return_value=mock_context_manager,
    )
    yield mock_registry_container


@pytest.fixture
def patch_util_inspect_image(mocker: MockFixture):
    """Patch the inspect_image function to return predefined metadata."""

    inspection_metadata = ImageToolsInspectionMetadata.model_validate(
        {
            "schemaVersion": 2,
            "mediaType": "application/vnd.oci.image.index.v1+json",
            "digest": "sha256:b49a0ec1a3a9a1c4fa65e6dd3004c981e0f1f1a495132da2e7a92fed8a3e5f4f",
            "size": 647,
            "manifests": [
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": "sha256:fc264c81b11b3310b4231b552d6b38239569b559a983cb2886623b83f5252261",
                    "size": 2765,
                    "platform": {"architecture": "amd64", "os": "linux"},
                },
                {
                    "mediaType": "application/vnd.oci.image.manifest.v1+json",
                    "digest": "sha256:0253116f6e3c69e371d32fb857e4f03f2537b28f276847115cce97be744f351d",
                    "size": 2765,
                    "platform": {"architecture": "arm64", "os": "linux"},
                },
            ],
        }
    )
    mock_inspect = mocker.patch(
        "posit_bakery.image.image_target.inspect_image",
        return_value=inspection_metadata,
    )
    yield mock_inspect


@pytest.fixture
def patch_docker_pull(mocker: MockFixture):
    """Patch docker.pull() to prevent actual image pulling during tests."""
    import python_on_whales

    mock_pull = mocker.patch.object(
        python_on_whales.docker.image,
        "pull",
        return_value=None,
    )
    yield mock_pull


@pytest.fixture
def patch_docker_tag(mocker: MockFixture):
    """Patch docker.tag() to prevent actual image tagging during tests."""
    import python_on_whales

    mock_tag = mocker.patch.object(
        python_on_whales.docker.image,
        "tag",
        return_value=None,
    )
    yield mock_tag


@pytest.fixture
def patch_docker_push(mocker: MockFixture):
    """Patch docker.push() to prevent actual image pushing during tests."""
    import python_on_whales

    mock_push = mocker.patch.object(
        python_on_whales.docker.image,
        "push",
        return_value=None,
    )
    yield mock_push


@pytest.fixture
def basic_standard_image_target(get_config_obj):
    """Return a standard ImageTarget object for testing."""
    basic_config_obj = get_config_obj("basic")

    image = basic_config_obj.model.get_image("test-image")
    version = image.get_version("1.0.0")
    variant = image.get_variant("Standard")
    os = version.os[0]

    return ImageTarget.new_image_target(
        repository=basic_config_obj.model.repository,
        image_version=version,
        image_variant=variant,
        image_os=os,
    )


@pytest.fixture
def basic_minimal_image_target(get_config_obj):
    """Return a standard ImageTarget object for testing."""
    basic_config_obj = get_config_obj("basic")

    image = basic_config_obj.model.get_image("test-image")
    version = image.get_version("1.0.0")
    variant = image.get_variant("Minimal")
    os = version.os[0]

    return ImageTarget.new_image_target(
        repository=basic_config_obj.model.repository,
        image_version=version,
        image_variant=variant,
        image_os=os,
    )
