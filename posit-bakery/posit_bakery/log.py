import logging

import typer
from rich.console import Console
from rich.logging import RichHandler

stdout_console = Console()
stderr_console = Console(stderr=True)


def init_logging(log_level: str | int = logging.INFO) -> None:
    """Initialize logging for the Bakery CLI

    :param log_level: The log level to use
    """

    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=stderr_console,
                markup=True,
                rich_tracebacks=True,
                tracebacks_suppress=[typer],
                tracebacks_max_frames=5,
            ),
        ],
    )
