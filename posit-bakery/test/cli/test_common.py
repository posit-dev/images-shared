from typing import List, Optional

import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from typer.testing import CliRunner, Result

from posit_bakery.main import app


scenarios("cli/bakery.feature")
scenarios("cli/new.feature")

runner = CliRunner()


class BakeryCommand:
    """Class representing a bakery command"""

    _subcommand: Optional[str]
    _flags: List[str]
    _args: List[str]
    _opts: List[str]
    result: Result

    def __init__(self):
        self._flags = []
        self._args = []
        self._opts = []

    def __str__(self):
        return "bakery " + " ".join(self.command)

    @property
    def command(self):
        _cmd = [self._subcommand] if self._subcommand else []
        return _cmd + self._flags + self._args + self._opts

    def add_args(self, args: List[str]):
        self._args.extend(args)

    def add_flag(self, flag: str):
        self._flags.append(f"--{flag}")

    def add_opt(self, name: str, value: str):
        self._opts.extend([f"--{name}", f"{value}"])

    def run(self):
        self.result = runner.invoke(app, self.command)


@pytest.fixture
def bakery_command():
    return BakeryCommand()


@given("I run bakery")
def bare_command(bakery_command):
    bakery_command._subcommand = None


# Construct the bakery command and all arguments
@given(parsers.parse('I run bakery "{command}"'))
def build_command(bakery_command, command):
    bakery_command._subcommand = command


@given(parsers.parse('with the "{args}" arguments'))
def add_args(bakery_command, args):
    bakery_command.add_args(args.split())


@given(parsers.parse('with the "{flag}" flag'))
def add_flag(bakery_command, flag):
    bakery_command.add_flag(flag)


@given(parsers.parse('with the "{opt}" option set to "{value}"'))
def add_option(bakery_command, opt, value):
    bakery_command.add_opt(opt, value)


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


@then("help is shown")
def check_help(bakery_command):
    # TODO: Make this check more robust, with options for specific output
    assert "Usage:" in bakery_command.result.stdout
