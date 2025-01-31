from pytest_bdd import scenarios, then, parsers

scenarios("cli/basic_context.feature")


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
