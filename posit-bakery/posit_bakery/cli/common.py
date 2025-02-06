from typing import Annotated, Optional

import typer

from posit_bakery.log import init_logging, stdout_console


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

    init_logging(verbose=verbose, quiet=quiet)
