import logging
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery import error
from posit_bakery.log import init_logging, stdout_console, stderr_console
from posit_bakery.models import Project


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


def __wrap_project_load(context: Path) -> Project:
    try:
        project = Project.load(context)
    except error.BakeryFileError:
        stderr_console.print_exception(max_frames=0, show_locals=False)
        stderr_console.print(f"❌ Failed to load project from '{context}'", style="error")
        stderr_console.print(
            "Please ensure you have a valid project in the specified directory.", style="info"
        )
        raise typer.Exit(code=1)
    except error.BakeryBadImageError:
        stderr_console.print_exception(max_frames=0, show_locals=False)
        stderr_console.print(f"❌ Failed to load project from '{context}'", style="error")
        stderr_console.print("Please correct the above error and try again.", style="info")
        raise typer.Exit(code=1)
    except (error.BakeryModelValidationError, error.BakeryModelValidationErrorGroup) as e:
        stderr_console.print(e)
        stderr_console.print(f"❌ Failed to load project from '{context}'", style="error")
        stderr_console.print(
            "Please correct the above data validation error(s) and try again.", style="info"
        )
        raise typer.Exit(code=1)
    except error.BakeryError:
        stderr_console.print_exception(max_frames=5)
        stderr_console.print(f"❌ Failed to load project from '{context}'", style="error")
        raise typer.Exit(code=1)
    except Exception:
        stderr_console.print_exception(max_frames=20)
        stderr_console.print(f"❌ Failed to load project from '{context}'", style="error")
        raise typer.Exit(code=1)
    return project
