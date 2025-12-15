import functools
import inspect
import logging
import tempfile
from pathlib import Path
from typing import Annotated, Optional, Any

import typer

from posit_bakery.log import init_logging, stderr_console
from posit_bakery.settings import SETTINGS

log = logging.getLogger(__name__)


def with_verbosity_flags(fn):
    @functools.wraps(fn)
    def wrapper(
        *args,
        verbose: Annotated[Optional[bool], typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
        quiet: Annotated[
            Optional[bool], typer.Option("--quiet", "-q", help="Supress all output except errors")
        ] = False,
        **kwargs,
    ):
        if verbose and quiet:
            raise typer.BadParameter("Cannot set both --debug and --quiet flags.")

        log_level: str | int = logging.INFO
        if verbose:
            log_level = logging.DEBUG
        elif quiet:
            log_level = logging.ERROR

        init_logging(log_level)
        return fn(*args, **kwargs)

    # Update signature with verbosity flags
    sig = inspect.signature(wrapper)
    params = list(sig.parameters.values())
    params.extend(
        [
            inspect.Parameter(
                "verbose",
                inspect.Parameter.KEYWORD_ONLY,
                default=False,
                annotation=Annotated[Optional[bool], typer.Option("--verbose", "-v", help="Enable debug logging")],
            ),
            inspect.Parameter(
                "quiet",
                inspect.Parameter.KEYWORD_ONLY,
                default=False,
                annotation=Annotated[
                    Optional[bool], typer.Option("--quiet", "-q", help="Supress all output except errors")
                ],
            ),
        ]
    )
    sig = sig.replace(parameters=params)
    wrapper.__signature__ = sig

    return wrapper


def with_temporary_storage(fn):
    @functools.wraps(fn)
    def wrapper(ctx: typer.Context, *args, **kwargs) -> None:
        temp_dir = tempfile.TemporaryDirectory(prefix="posit-bakery")
        SETTINGS.temporary_storage = Path(temp_dir.name)
        if ctx.params.get("clean", True) or ctx.params.get("no-clean", False):
            ctx.call_on_close(temp_dir.cleanup)

        log.debug(f"Created temporary directory at {SETTINGS.temporary_storage}")

        return fn(*args, **kwargs)

    # Update signature with verbosity flags
    sig = inspect.signature(wrapper)
    params = list(sig.parameters.values())
    params.insert(0, inspect.Parameter("ctx", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=typer.Context))
    sig = sig.replace(parameters=params)
    wrapper.__signature__ = sig

    return wrapper


def __make_value_map(value: list[str] | None) -> dict[Any, Any]:
    """Parses key=value option pairs into a dictionary"""
    value_map = dict()
    if value is not None:
        for v in value:
            sp = v.split("=", 1)
            if len(sp) != 2:
                stderr_console.print(f"❌ Expected key=value pair, got [bold]'{v}'", style="error")
                raise typer.Exit(code=1)
            value_map[sp[0]] = sp[1]
    return value_map
