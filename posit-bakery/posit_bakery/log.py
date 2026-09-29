import logging
import os
import sys

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

default_theme = Theme(
    {
        "info": "bright_blue",
        "error": "bright_red",
        "success": "green3",
        "quiet": "bright_black",
        "quiet_italicized": "bright_black italic",
    }
)

# Rich falls back to 80 columns when output is not a TTY and COLUMNS is unset (e.g. GitHub Actions),
# which squashes tables. Use a wider default there; a real terminal or COLUMNS still takes precedence.
NON_TTY_DEFAULT_WIDTH = 160


def _console_width(stream) -> int | None:
    if os.environ.get("COLUMNS") or stream.isatty():
        return None
    return NON_TTY_DEFAULT_WIDTH


stdout_console = Console(theme=default_theme, width=_console_width(sys.stdout))
stderr_console = Console(stderr=True, theme=default_theme, width=_console_width(sys.stderr))


def init_logging(log_level: str | int = logging.INFO) -> None:
    """Initialize logging for the Bakery CLI

    :param log_level: The log level to use
    """
    tb_frames = 0
    if log_level == logging.DEBUG:
        tb_frames = 20

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
                tracebacks_max_frames=tb_frames,
                tracebacks_show_locals=True if log_level == logging.DEBUG else False,
            ),
        ],
    )
