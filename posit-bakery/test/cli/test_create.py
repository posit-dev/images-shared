from pytest_bdd import scenarios, then, parsers

from posit_bakery.models import Manifest

scenarios(
    "cli/create/project.feature",
    "cli/create/image.feature",
    "cli/create/version.feature",
)


@then("config.yaml exists")
def check_config_file(bakery_command):
    config_file = bakery_command.context / "config.yaml"
    assert config_file.is_file()


@then(parsers.parse('the image "{image_name}" exists'), target_fixture="new_image_name")
def check_image(basic_tmpcontext, image_name) -> str:
    image_dir = basic_tmpcontext / image_name
    assert image_dir.is_dir()
    assert (image_dir / "manifest.yaml").is_file()

    return image_name


@then(parsers.parse('the version "{version}" exists'), target_fixture="new_version")
def check_version(basic_tmpcontext, version, new_image_name) -> str:
    image_dir = basic_tmpcontext / new_image_name
    manifest_file = image_dir / "manifest.yaml"
    assert manifest_file.is_file()

    version_dir = image_dir / version
    assert version_dir.is_dir()

    manifest = Manifest.load(manifest_file)
    assert version in manifest.model.build
    assert manifest.model.build[version].latest == True
    assert "Ubuntu 22.04" in manifest.model.build[version].os

    assert "1.0.0" in manifest.model.build
    assert manifest.model.build["1.0.0"].latest == False

    return version


@then(parsers.parse("the default templates exist"))
def check_default_templates(basic_tmpcontext, new_image_name) -> None:
    image_dir = basic_tmpcontext / new_image_name
    template_dir = image_dir / "template"
    assert template_dir.is_dir()

    containerfile = template_dir / f"Containerfile.jinja2"
    assert containerfile.is_file()

    test = template_dir / "test"
    assert test.is_dir()
    assert (test / "goss.yaml.jinja2").is_file()

    deps = template_dir / "deps"
    assert deps.is_dir()
    assert (deps / f"packages.txt.jinja2").is_file()


@then(parsers.parse('the default base image is "{base_image}"'))
def check_base_image(basic_tmpcontext, base_image, new_image_name) -> None:
    files = list((basic_tmpcontext / new_image_name / "template").rglob("Containerfile*jinja2"))

    assert len(files) == 1
    assert f"FROM {base_image}" in files[0].read_text()


@then("the default rendered templates exist")
def check_rendered_templates(basic_tmpcontext, new_image_name, new_version) -> None:
    version_dir = basic_tmpcontext / new_image_name / new_version
    _os = "ubuntu2204"

    min = version_dir / f"Containerfile.{_os}.min"
    assert min.is_file()
    min_contents = min.read_text()
    assert f'ARG IMAGE_VERSION="{new_version}"' in min_contents
    assert f"{_os}_optional_packages.txt" not in min_contents

    std = version_dir / f"Containerfile.{_os}.std"
    assert std.is_file()
    std_contents = std.read_text()
    assert f'ARG IMAGE_VERSION="{new_version}"' in std_contents
    assert f"{_os}_optional_packages.txt" in std_contents

    deps = version_dir / "deps"
    assert deps.is_dir()
    assert (deps / "ubuntu2204_packages.txt").is_file()
    assert (deps / "ubuntu2204_optional_packages.txt").is_file()

    test = version_dir / "test"
    assert test.is_dir()
    assert (test / "goss.yaml").is_file()
