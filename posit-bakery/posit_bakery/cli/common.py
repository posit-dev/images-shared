import logging
from typing import Annotated, Optional, Any

import typer

from posit_bakery.log import init_logging, stdout_console, stderr_console


def __version_callback(value: bool) -> None:
    if value:
        from posit_bakery import __version__

        stdout_console.print(f"Posit Bakery v{__version__}", highlight=False)
        raise typer.Exit()


def __global_flags(
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version", "-V", is_eager=True, callback=__version_callback, help="Display the version of Posit Bakery"
        ),
    ] = False,
    verbose: Annotated[Optional[bool], typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="Supress all output except errors")] = False,
) -> None:
    """Callback to configure global flags"""
    if verbose and quiet:
        raise typer.BadParameter("Cannot set both --debug and --quiet flags.")

    log_level: str | int = logging.INFO
    if verbose:
        log_level = logging.DEBUG
    elif quiet:
        log_level = logging.ERROR

    init_logging(log_level)


def __make_value_map(value: list[str] | None) -> dict[Any, Any]:
    # Parse the key=value pairs into a dictionary
    value_map = dict()
    if value is not None:
        for v in value:
            sp = v.split("=", 1)
            if len(sp) != 2:
                stderr_console.print(f"❌ Expected key=value pair, got [bold]'{v}'", style="error")
                raise typer.Exit(code=1)
            value_map[sp[0]] = sp[1]
    return value_map
