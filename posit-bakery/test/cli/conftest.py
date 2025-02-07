# conftest.py loads this file via pytest_plugins
import json
from pathlib import Path

import pytest
from pytest_bdd import given, when, then, parsers

from test.cli.bakery_command import BakeryCommand


@pytest.fixture
def bakery_command():
    return BakeryCommand()


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
    bakery_command.context = Path(basic_context)


@given("in a temp basic context")
def tmp_context(bakery_command, basic_tmpcontext):
    bakery_command.context = Path(basic_tmpcontext)


@given("in a temp directory")
def tmp_directory(bakery_command, tmpdir):
    bakery_command.context = Path(tmpdir)


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
