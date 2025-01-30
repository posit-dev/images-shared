import json
from typing import List, Optional

import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from typer.testing import CliRunner, Result

from posit_bakery.main import app


scenarios("cli/bakery.feature")
scenarios("cli/new.feature")
scenarios("cli/plan.feature")

runner = CliRunner()


class BakeryCommand:
    """Class representing a bakery command"""

    _subcommand: Optional[str]
    _args: List[str]
    result: Result

    def __init__(self):
        self._args = []

    def __str__(self):
        return "bakery " + " ".join(self.command)

    @property
    def command(self):
        _cmd = [self._subcommand] if self._subcommand else []
        return _cmd + self._args

    def add_args(self, args: List[str]):
        # Filter out empty strings
        args = [a for a in args if a]
        self._args.extend(args)

    def run(self):
        self.result = runner.invoke(app, self.command)


@pytest.fixture
def bakery_command():
    return BakeryCommand()


# Construct the bakery command and all arguments
@given("I call bakery")
def bare_command(bakery_command):
    bakery_command._subcommand = None


@given(parsers.parse('I call bakery "{command}"'))
def build_command(bakery_command, command):
    bakery_command._subcommand = command


@given("with the basic context")
def basic_context(bakery_command, basic_tmpcontext):
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
    # TODO: Make this check more robust, with options for specific output
    assert "Usage:" in bakery_command.result.stdout


@then("an error message is shown")
def check_error(bakery_command):
    assert "Error" in bakery_command.result.stdout


@then("the output includes:")
def check_stdout(bakery_command, datatable):
    for row in datatable:
        assert row[0] in bakery_command.result.stdout


@then("the output is JSON")
def check_json(bakery_command):
    """
    Check that the output is valid JSON

    An exception will be raised if the output is not valid JSON
    """
    json.loads(bakery_command.result.stdout)
