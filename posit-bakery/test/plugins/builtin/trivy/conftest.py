import pytest

from posit_bakery.image import ImageTarget


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
