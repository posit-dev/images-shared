# conftest.py loads this file via pytest_plugins
import os
import shutil
from pathlib import Path
from typing import List

import pytest
from pytest_bdd import given, when, then, parsers

from test.cli.bakery_command import BakeryCommand
from test.helpers import remove_images


@pytest.fixture(scope="session")
def ci_testdata():
    """Return the path to the CI test data directory"""
    return Path(__file__).parent / "testdata"


def pytest_bdd_apply_tag(tag, function):
    """Modify scenario tags to be pytest-compatible."""
    if tag == "xdist-build":
        marker = pytest.mark.xdist_group("build")
        marker(function)
        return True
    else:
        return None


@pytest.fixture
def bakery_command():
    return BakeryCommand()


# Construct the bakery command and all arguments
@given("I call bakery")
def bare_command(bakery_command):
    bakery_command.reset()


@given(parsers.cfparse("I call bakery {commands:String*}", extra_types={"String": str}))
def sub_command(bakery_command, commands: List[str]):
    bakery_command.reset()
    parsed_commands = []
    for command in commands:
        parsed_commands.extend(command.split())  # FIXME: pytest-bdd is unclear on how to natively autosplit this
    bakery_command.set_subcommand(parsed_commands)


@given(parsers.parse("in the {suite_name} context"))
def cli_context(bakery_command, suite_name, get_context):
    bakery_command.context = Path(get_context(suite_name))


@given(parsers.parse("in a temp {suite_name} context"), target_fixture="cli_test_tmpcontext")
def cli_tmpcontext(bakery_command, suite_name, get_tmpcontext):
    bakery_command.context = Path(get_tmpcontext(suite_name))

    return Path(get_tmpcontext(suite_name))


@given("with the context as the working directory")
def cli_tmpcontext(bakery_command):
    original_wd = os.getcwd()
    os.chdir(bakery_command.context)
    yield
    os.chdir(original_wd)


@given("in a temp directory")
def tmp_directory(bakery_command, tmpdir):
    bakery_command.context = Path(tmpdir)


@given(parsers.parse("with the '{target_path}' path removed"))
def remove_path(bakery_command, target_path, cli_test_tmpcontext):
    target_path = (cli_test_tmpcontext / target_path).resolve()
    if target_path.exists():
        if target_path.is_dir():
            shutil.rmtree(target_path)
        else:
            target_path.unlink()
    else:
        pytest.fail(f"Path {target_path} does not exist to be removed")

    assert not target_path.exists()


@given("with the arguments:")
def add_args_table(bakery_command, datatable):
    for row in datatable:
        bakery_command.add_args(row)


# Run the command
@when("I execute the command", target_fixture="command_logs")
def run(bakery_command, caplog):
    bakery_command.run()
    return caplog


# Check the results of the command
@then("The command succeeds")
def check_success(bakery_command):
    assert bakery_command.result.exit_code == 0


@then(parsers.parse("The command exits with code {exit_code:d}"))
def check_exit_code(bakery_command, exit_code: int):
    assert bakery_command.result.exit_code == exit_code


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


@then("the context includes file:")
@then("the context includes files:")
def check_context(bakery_command, datatable):
    for row in datatable:
        test_path = bakery_command.context / row[0]
        assert test_path.exists()


@then(parsers.parse("the {suite_name} images are removed"))
def remove_build_artifacts(request, resource_path, bakery_command, suite_name, get_config_obj):
    config_obj = get_config_obj(suite_name)
    remove_images(config_obj)
