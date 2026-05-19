import pytest

from posit_bakery.image import ImageTarget


@pytest.fixture(autouse=True)
def _clear_github_env(monkeypatch):
    """Drop the runner's GITHUB_ACTIONS and GITHUB_TOKEN so the dgoss command's
    GH_TOKEN forwarding does not leak into tests that assert exact env/cmd
    contents. Tests that exercise the forwarding behaviour set them explicitly."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)


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
