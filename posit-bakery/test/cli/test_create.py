from pathlib import Path

from pytest_bdd import scenarios, then, parsers

from posit_bakery.config import BakeryConfig

scenarios(
    "cli/create/project.feature",
    "cli/create/image.feature",
    "cli/create/version.feature",
)


@then("bakery.yaml exists")
def check_bakery_file(bakery_command):
    config_file = bakery_command.context / "bakery.yaml"
    assert config_file.is_file()


@then(parsers.parse('the image "{image_name}" exists'), target_fixture="cli_test_image_name")
@then(parsers.parse('the image "{image_name}" exists in the "{subpath}" subpath'), target_fixture="cli_test_image_name")
def check_image(cli_test_tmpcontext, image_name, subpath=None) -> str:
    image_dir = cli_test_tmpcontext / image_name
    if subpath:
        image_dir = cli_test_tmpcontext / Path(subpath)
    assert image_dir.is_dir()
    tpl_dir = image_dir / "template"
    assert tpl_dir.is_dir()

    return image_name


@then(parsers.parse('the version "{version}" exists'), target_fixture="cli_test_version")
@then(parsers.parse('the version "{version}" exists in the "{subpath}" subpath'), target_fixture="cli_test_version")
def check_version(cli_test_tmpcontext, version, cli_test_image_name, subpath=None) -> str:
    config = BakeryConfig.from_context(cli_test_tmpcontext)
    image = config.model.get_image(cli_test_image_name)

    version_dir = image.path / version
    if subpath:
        version_dir = image.path / Path(subpath)
    assert version_dir.is_dir()

    assert image.get_version(version) is not None
    assert image.get_version(version).latest
    assert image.get_version(version).os[0].name == "Ubuntu 22.04"

    return version


@then(parsers.parse("the default templates exist"))
@then(parsers.parse('the default templates exist in the "{subpath}" subpath'))
def check_default_templates(cli_test_tmpcontext, cli_test_image_name, subpath=None) -> None:
    image_dir = cli_test_tmpcontext / cli_test_image_name
    if subpath:
        image_dir = cli_test_tmpcontext / Path(subpath)
    template_dir = image_dir / "template"
    assert template_dir.is_dir()

    containerfile = template_dir.glob(f"Containerfile*jinja2")
    assert len(list(containerfile)) == 1

    test = template_dir / "test"
    assert test.is_dir()
    assert (test / "goss.yaml.jinja2").is_file()

    deps = template_dir / "deps"
    assert deps.is_dir()
    assert (deps / f"packages.txt.jinja2").is_file()


@then(parsers.parse('the default base image is "{base_image}"'))
@then(parsers.parse('the default base image is "{base_image}" in the "{subpath}" subpath'))
def check_base_image(cli_test_tmpcontext, base_image, cli_test_image_name, subpath=None) -> None:
    files = list((cli_test_tmpcontext / cli_test_image_name / "template").rglob("Containerfile*jinja2"))
    if subpath:
        files = list((cli_test_tmpcontext / Path(subpath) / "template").rglob("Containerfile*jinja2"))

    assert len(files) == 1
    assert f"FROM {base_image}" in files[0].read_text()


@then("the default rendered templates exist")
@then(parsers.parse('the default rendered templates exist in the "{subpath}" subpath'))
def check_rendered_templates(cli_test_tmpcontext, cli_test_image_name, cli_test_version, subpath=None) -> None:
    version_dir = cli_test_tmpcontext / cli_test_image_name / cli_test_version
    if subpath:
        version_dir = cli_test_tmpcontext / cli_test_image_name / Path(subpath)
    _os = "ubuntu2204"

    min = version_dir / f"Containerfile.{_os}.min"
    assert min.is_file()
    min_contents = min.read_text()
    assert f'ARG IMAGE_VERSION="{cli_test_version}"' in min_contents
    assert f"{_os}_optional_packages.txt" not in min_contents

    std = version_dir / f"Containerfile.{_os}.std"
    assert std.is_file()
    std_contents = std.read_text()
    assert f'ARG IMAGE_VERSION="{cli_test_version}"' in std_contents
    assert f"{_os}_optional_packages.txt" in std_contents

    deps = version_dir / "deps"
    assert deps.is_dir()
    assert (deps / "ubuntu2204_packages.txt").is_file()
    assert (deps / "ubuntu2204_optional_packages.txt").is_file()

    test = version_dir / "test"
    assert test.is_dir()
    assert (test / "goss.yaml").is_file()
