import datetime
from unittest.mock import Mock, MagicMock

import pytest
from pytest_mock import MockFixture

from posit_bakery.image import ImageTarget

CONST_DATETIME_NOW = datetime.datetime(2025, 1, 1, 0, 0, 0)


@pytest.fixture
def datetime_now_value():
    """Return a fixed datetime for testing."""
    return CONST_DATETIME_NOW


@pytest.fixture
def patch_datetime_now(mocker: MockFixture, datetime_now_value):
    """Mock datetime.now() to return a fixed datetime for testing."""
    import posit_bakery.image.image_target

    mocked_datetime = mocker.patch(
        "posit_bakery.image.image_target.datetime",
    )
    mock_datetime_now = MagicMock(spec=datetime_now_value)
    mocked_datetime.now = mock_datetime_now
    mock_datetime_now.return_value = datetime_now_value
    mock_datetime_now.isoformat.return_value = datetime_now_value.isoformat()
    yield mocked_datetime


@pytest.fixture
def basic_standard_image_target(basic_unified_config_obj):
    """Return a standard ImageTarget object for testing."""

    image = basic_unified_config_obj.model.get_image("test-image")
    version = image.get_version("1.0.0")
    variant = image.get_variant("Standard")
    os = version.os[0]

    return ImageTarget.new_image_target(
        repository=basic_unified_config_obj.model.repository,
        image_version=version,
        image_variant=variant,
        image_os=os,
    )


@pytest.fixture
def basic_minimal_image_target(basic_unified_config_obj):
    """Return a standard ImageTarget object for testing."""

    image = basic_unified_config_obj.model.get_image("test-image")
    version = image.get_version("1.0.0")
    variant = image.get_variant("Minimal")
    os = version.os[0]

    return ImageTarget.new_image_target(
        repository=basic_unified_config_obj.model.repository,
        image_version=version,
        image_variant=variant,
        image_os=os,
    )
