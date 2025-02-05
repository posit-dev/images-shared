import logging

import typer
from rich.console import Console
from rich.logging import RichHandler

stdout_console = Console()
stderr_console = Console(stderr=True)


def init_logging(verbose: bool = False, quiet: bool = False) -> None:
    """Initialize logging for the Bakery CLI

    :param verbose: Enable debug logging
    :param quiet: Suppress all output except errors
    """
    level = "INFO"
    if verbose:
        level = "DEBUG"
    elif quiet:
        level = "ERROR"

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(console=stderr_console, markup=True, rich_tracebacks=True, tracebacks_suppress=[typer]),
        ],
    )