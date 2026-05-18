"""Click-compatible export of the Typer CLI for great-docs reference generation.

great-docs expects a `click.Command` or `click.Group` and reads help text via
`Command.get_help()`. The runtime CLI is a `typer.Typer`; `typer.main.get_command`
returns a Click-compatible object, but Typer's Rich help override writes to the
console and returns an empty string. Setting `rich_markup_mode=None` on every
group makes Typer fall back to Click's standard formatter, which returns the
rendered help as a string. This affects only the docs-time export.
"""

import click
import typer
from typer.core import TyperCommand, TyperGroup

from posit_bakery.cli.main import app


def _disable_rich_help(cmd: click.Command) -> None:
    if isinstance(cmd, (TyperGroup, TyperCommand)):
        cmd.rich_markup_mode = None
    if isinstance(cmd, click.Group):
        for sub in cmd.commands.values():
            _disable_rich_help(sub)


def _stabilize_path_defaults(cmd: click.Command) -> None:
    # `--context` defaults to the cwd captured at import time (auto_path()),
    # which would leak the docs-build directory into rendered help. Render a
    # stable placeholder instead.
    for param in getattr(cmd, "params", []):
        if param.name == "context":
            param.show_default = "."
    if isinstance(cmd, click.Group):
        for sub in cmd.commands.values():
            _stabilize_path_defaults(sub)


click_app = typer.main.get_command(app)
_disable_rich_help(click_app)
_stabilize_path_defaults(click_app)
