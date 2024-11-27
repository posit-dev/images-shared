from typing import List, Optional

import pytest
from pytest_bdd import scenarios, given, when, then, parsers

scenarios("../features/new.feature")

class BakeryCommand:
    """Class representing a bakery command"""
    _command: str
    _flags: List[str]
    _args: List[str]
    _opts: List[str]

    def __init__(self):
        self._flags = []
        self._args = []
        self._opts = []

    def __str__(self):
        return " ".join(self.command)

    @property
    def command(self):
        return ["bakery", self._command] + self._flags + self._args + self._opts

    def add_args(self, args: List[str]):
        self._args.extend(args)

    def add_flag(self, flag: str):
        self._flags.append(f"--{flag}")

    def add_opt(self, name: str, value: str):
        self._opts.extend([f"--{name}", f"{value}"])

    def run(self):
        print(f"Running command: {self}")
        raise NotImplementedError


@pytest.fixture
def bakery_command():
    return BakeryCommand()


# Construct the bakery command and all arguments
@given(parsers.parse('I run bakery "{command}"'))
def build_command(bakery_command, command):
    bakery_command._command = command

@given(parsers.parse('with the arguments "{args}"'))
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
