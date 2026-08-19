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


@pytest.fixture
def no_variant_image_target(get_config_obj):
    """Return a variant-less ImageTarget with image-level tool options set.

    Regression fixture for posit-dev/images-shared#756: image-level `options:` must not be
    silently ignored for images with no `variants:` entries.
    """
    config_obj = get_config_obj("variant-less-options")

    image = config_obj.model.get_image("no-variant-image")
    version = image.get_version("1.0.0")
    os = version.os[0]

    return ImageTarget.new_image_target(
        repository=config_obj.model.repository,
        image_version=version,
        image_variant=None,
        image_os=os,
    )
