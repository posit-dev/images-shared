from typing import Annotated, Optional

import typer

from posit_bakery.cli.main import app
from posit_bakery.log import init_logging


@app.callback()
def __callback_logging(
    debug: Annotated[Optional[bool], typer.Option("--debug", "-d", help="Enable debug logging")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="Supress all output except errors")] = False,
) -> None:
    """Callback to configure logging based on the debug and quiet flags."""
    if debug and quiet:
        raise typer.BadParameter("Cannot set both --debug and --quiet flags.")

    init_logging(debug=debug, quiet=quiet)
