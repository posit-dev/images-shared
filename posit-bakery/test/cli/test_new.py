from pytest_bdd import scenarios, given, when, then, parsers

scenarios("cli/new.feature")


@then(parsers.parse('the image "{image_name}" exists'), target_fixture="new_image_name")
def check_image_directory(basic_tmpcontext, image_name) -> str:
    image_dir = basic_tmpcontext / image_name
    assert image_dir.is_dir()
    assert (image_dir / "manifest.toml").is_file()

    return image_name


@then(parsers.parse("the default templates exist"))
def check_default_templates(basic_tmpcontext, new_image_name) -> None:
    image_dir = basic_tmpcontext / new_image_name
    image_template_path = image_dir / "template"
    assert image_template_path.is_dir()

    containerfile = image_template_path / f"Containerfile.jinja2"
    assert containerfile.is_file()

    test = image_template_path / "test"
    assert test.is_dir()
    assert (test / "goss.yaml.jinja2").is_file()

    deps = image_template_path / "deps"
    assert deps.is_dir()
    assert (deps / f"packages.txt.jinja2").is_file()


@then(parsers.parse('the default base image is "{base_image}"'))
def check_base_image(basic_tmpcontext, base_image, new_image_name) -> None:
    files = list((basic_tmpcontext / new_image_name / "template").rglob("Containerfile*jinja2"))

    assert len(files) == 1
    assert f"FROM {base_image}" in files[0].read_text()
