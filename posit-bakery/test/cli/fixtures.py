# conftest.py loads this file via pytest_plugins
from typing import List

import pytest
from typer.testing import CliRunner, Result

from posit_bakery.cli.main import app


runner = CliRunner(mix_stderr=False)


class BakeryCommand:
    """Class representing a bakery command"""

    def __init__(self):
        self.args: List[str] = []
        self.subcommand: List[str] | None = None
        self.result: Result | None = None

    def __str__(self):
        return "bakery " + " ".join(self.clirunner_args)

    def set_subcommand(self, subcommand: List[str] | str = None):
        if type(subcommand) is str:
            subcommand = [subcommand]
        self.subcommand = subcommand

    @property
    def clirunner_args(self):
        return self.subcommand + self.args

    def add_args(self, args: List[str]):
        # Filter out empty strings
        args = [a for a in args if a]
        self.args.extend(args)

    def run(self):
        self.result = runner.invoke(app, self.clirunner_args, catch_exceptions=True)


@pytest.fixture
def bakery_command():
    return BakeryCommand()
