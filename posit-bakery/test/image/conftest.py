from pathlib import Path

import pytest
from pytest_mock import MockFixture

from posit_bakery.image import ImageTarget


@pytest.fixture
def image_testdata():
    """Return the path to the image testdata directory."""
    return Path(__file__).parent / "testdata"


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
