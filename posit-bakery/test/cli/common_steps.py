# conftest.py loads this file via pytest_plugins
import json

import pytest
from pytest_bdd import given, when, then, parsers

from posit_bakery.models import Manifest


# Construct the bakery command and all arguments
@given("I call bakery")
def bare_command(bakery_command):
    bakery_command.reset()


@given(parsers.parse('I call bakery "{command}"'))
def top_level_command(bakery_command, command):
    bakery_command.reset()
    bakery_command.set_subcommand(command)
    

@given(parsers.parse('I call bakery "{subgroup}" "{subcommand}"'))
def subgroup_command(bakery_command, subgroup, subcommand):
    bakery_command.reset()
    bakery_command.set_subcommand([subgroup, subcommand])


@given("in the basic context")
def basic_context(bakery_command, basic_context):
    bakery_command.add_args(["--context", str(basic_context)])


@given("in a temp basic context")
def tmp_context(bakery_command, basic_tmpcontext):
    bakery_command.add_args(["--context", str(basic_tmpcontext)])


@given("with the arguments:")
def add_args_table(bakery_command, datatable):
    for row in datatable:
        bakery_command.add_args(row)


# Run the command
@when("I execute the command")
def run(bakery_command):
    bakery_command.run()


# Check the results of the command
@then("The command succeeds")
def check_success(bakery_command):
    assert bakery_command.result.exit_code == 0


@then("The command fails")
def check_failure(bakery_command):
    assert bakery_command.result.exit_code != 0


@then("usage is shown")
def check_usage(bakery_command):
    assert "Usage:" in bakery_command.result.stderr


@then("help is shown")
def check_help(bakery_command):
    assert "Usage:" in bakery_command.result.stdout
    assert "Options" in bakery_command.result.stdout


@then("an error message is shown")
def check_error(bakery_command):
    assert "Error" in bakery_command.result.stderr


@then("the stdout output includes:")
def check_stdout(bakery_command, datatable):
    for row in datatable:
        assert row[0] in bakery_command.result.stdout


@then("the stderr output includes:")
def check_stderr(bakery_command, datatable):
    for row in datatable:
        assert row[0] in bakery_command.result.stderr


@then("the log includes:")
def check_log(caplog, datatable):
    for row in datatable:
        assert row[0] in caplog.text


@then(parsers.parse('the image "{image_name}" exists'), target_fixture="new_image_name")
def check_image(basic_tmpcontext, image_name) -> str:
    image_dir = basic_tmpcontext / image_name
    assert image_dir.is_dir()
    assert (image_dir / "manifest.toml").is_file()

    return image_name


@then(parsers.parse('the version "{version}" exists'), target_fixture="new_version")
def check_version(basic_tmpcontext, version, new_image_name) -> str:
    image_dir = basic_tmpcontext / new_image_name
    manifest_file = image_dir / "manifest.toml"
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


@then("the bake plan is valid")
def check_json(bakery_command):
    try:
        plan = json.loads(bakery_command.result.stdout)
    except json.JSONDecodeError:
        pytest.fail("bakery plan output is not valid JSON")

    assert "group" in plan
    assert isinstance(plan["group"], dict)
    assert "default" in plan["group"]
    assert isinstance(plan["group"]["default"], dict)
    assert "targets" in plan["group"]["default"]
    assert isinstance(plan["group"]["default"]["targets"], list)

    assert "target" in plan
    assert isinstance(plan["target"], dict)


@then("the targets include the commit hash")
def check_revision(bakery_command):
    plan = json.loads(bakery_command.result.stdout)

    label: str = "org.opencontainers.image.revision"
    for target in plan["target"].values():
        assert label in target["labels"]
        assert target["labels"][label]


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
