# conftest.py loads this file via pytest_plugins
from typing import List

import pytest
from typer.testing import CliRunner, Result

from posit_bakery.cli import app


runner = CliRunner(mix_stderr=False)


class BakeryCommand:
    """Class representing a bakery command"""

    _subcommand: str | None
    _args: List[str]
    result: Result | None

    def __init__(self):
        self._args = []

    def __str__(self):
        return "bakery " + " ".join(self.command)

    @property
    def command(self):
        _cmd = [self._subcommand] if self._subcommand else []
        return _cmd + self._args

    def reset(self):
        self._subcommand = None
        self._args = []
        self.result = None

    def add_args(self, args: List[str]):
        # Filter out empty strings
        args = [a for a in args if a]
        self._args.extend(args)

    def run(self):
        self.result = runner.invoke(app, self.command)


@pytest.fixture
def bakery_command():
    return BakeryCommand()
