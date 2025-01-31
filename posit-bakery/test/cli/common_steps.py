# conftest.py loads this file via pytest_plugins
import json

import pytest
from pytest_bdd import given, when, then, parsers

from posit_bakery.models import Manifest


# Construct the bakery command and all arguments
@given("I call bakery")
def bare_command(bakery_command):
    bakery_command.reset()
    bakery_command._subcommand = None


@given(parsers.parse('I call bakery "{command}"'))
def sub_command(bakery_command, command):
    bakery_command.reset()
    bakery_command._subcommand = command


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
    assert "Usage:" in bakery_command.result.stdout


@then("an error message is shown")
def check_error(bakery_command):
    assert "Error" in bakery_command.result.stdout


@then("the output includes:")
def check_stdout(bakery_command, datatable):
    for row in datatable:
        assert row[0] in bakery_command.result.stdout


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
