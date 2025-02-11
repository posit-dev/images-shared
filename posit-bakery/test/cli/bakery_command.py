# conftest.py loads this file via pytest_plugins
from pathlib import Path
from typing import List

import pytest
from typer.testing import CliRunner, Result

from posit_bakery.cli.main import app


runner = CliRunner(mix_stderr=False)


class BakeryCommand:
    """Class representing a bakery command"""

    def __init__(self):
        self.args: List[str] = []
        self.subcommand: List[str] = []
        self.result: Result | None = None
        self.context: Path | None = None
        self.env: dict[str, str] = {"TERM": "dumb", "NO_COLOR": "true"}

    def __str__(self):
        return "bakery " + " ".join(self.clirunner_args)

    def __repr__(self):
        printable_result = None
        if self.result:
            if self.result.exception is not None:
                printable_result = f"Exception: {self.result.exception}"
            else:
                printable_result = f"Exit Code: {self.result.exit_code}"
        return f"<BakeryCommand<args = '{str(self)}', result = '{printable_result}'>>"

    def reset(self):
        self.args = []
        self.subcommand = []
        self.result = None
        self.context = None
        self.env: dict[str, str] = {"TERM": "dumb", "NO_COLOR": "true"}

    def set_subcommand(self, subcommand: List[str] | str = None):
        if type(subcommand) is str:
            subcommand = [subcommand]
        elif type(subcommand) is None:
            subcommand = []
        self.subcommand = subcommand

    @property
    def clirunner_args(self):
        args = []
        if self.subcommand:
            args.extend(self.subcommand)
        if self.context is not None:
            args.extend(["--context", str(self.context)])
        if self.args:
            args.extend(self.args)
        return args

    def add_args(self, args: List[str]):
        # Filter out empty strings
        args = [a for a in args if a]
        self.args.extend(args)

    def run(self):
        self.result = runner.invoke(app, self.clirunner_args, catch_exceptions=True, env=self.env)
