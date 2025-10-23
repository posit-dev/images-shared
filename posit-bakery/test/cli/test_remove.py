from pathlib import Path

from pytest_bdd import scenarios, then, parsers

from posit_bakery.config import BakeryConfig

scenarios(
    "cli/remove/image.feature",
    "cli/remove/version.feature",
)


@then(parsers.parse("the image '{image_name}' should not exist in the bakery config"))
def check_image_removed(bakery_command, image_name: str):
    """Check that the image was removed from the bakery config."""
    config = BakeryConfig.from_context(bakery_command.context)
    assert config.model.get_image(image_name) is None, f"Image '{image_name}' still exists in the bakery config."


@then(parsers.parse("the path '{image_path}' should not exist in the bakery context"))
def check_image_path_removed(bakery_command, image_path: str):
    """Check that the image path was removed from the bakery context."""
    full_path = bakery_command.context / image_path
    assert not full_path.exists(), f"Image path '{full_path}' still exists in the bakery context."


@then(parsers.parse("the version '{version_name}' in the '{image_name}' image should not exist in the bakery config"))
def check_version_removed(bakery_command, version_name: str, image_name: str):
    """Check that the version was removed from the bakery config."""
    config = BakeryConfig.from_context(bakery_command.context)
    image = config.model.get_image(image_name)
    assert image is not None, f"Image '{image_name}' does not exist in the bakery config."
    assert image.get_version(version_name) is None, f"Version '{version_name}' still exists in the bakery config."


@then(parsers.parse("the path '{version_path}' should not exist in the '{image_name}' image path"))
def check_version_path_removed(bakery_command, version_path: str, image_name: str):
    """Check that the version path was removed from the bakery context."""
    config = BakeryConfig.from_context(bakery_command.context)
    image = config.model.get_image(image_name)
    assert image is not None, f"Image '{image_name}' does not exist in the bakery config."
    full_path = image.path / version_path
    assert not full_path.exists(), f"Version path '{full_path}' still exists in the bakery context."
