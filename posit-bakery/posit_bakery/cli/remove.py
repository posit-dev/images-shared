import logging
from pathlib import Path
from typing import Annotated

import typer

from posit_bakery.cli.common import with_verbosity_flags
from posit_bakery.config import BakeryConfig
from posit_bakery.log import stderr_console
from posit_bakery.util import auto_path

app = typer.Typer(no_args_is_help=True)
log = logging.getLogger(__name__)


@app.command()
@with_verbosity_flags
def image(
    image_name: Annotated[
        str, typer.Argument(show_default=False, help="The image name to remove files and configurations for.")
    ],
    context: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            resolve_path=True,
            help="The root path to use. Defaults to the current working directory where invoked.",
        ),
    ] = auto_path(),
) -> None:
    """Removes an existing image from the bakery project

    Removes the image directory and all its contents from the bakery project and will remove its
    configuration from the bakery.yaml file.
    """
    try:
        c = BakeryConfig.from_context(context)
    except:
        log.exception("Error removing image, could not load project")
        stderr_console.print(f"❌ Failed to remove image '{image_name}'", style="error")
        raise typer.Exit(code=1)

    try:
        c.remove_image(image_name)
    except:
        log.exception("Error removing image")
        stderr_console.print(f"❌ Failed to remove image '{image_name}'", style="error")
        raise typer.Exit(code=1)

    stderr_console.print(f"✅ Successfully removed image '{image_name}'", style="success")


@app.command()
@with_verbosity_flags
def version(
    image_name: Annotated[
        str,
        typer.Argument(
            show_default=False,
            help="The image to which the version to be removed belongs. This must match an image name present in the "
            "bakery.yaml configuration.",
        ),
    ],
    image_version: Annotated[str, typer.Argument(show_default=False, help="The image version to remove.")],
    context: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            writable=True,
            resolve_path=True,
            help="The root path to use. Defaults to the current working directory where invoked.",
        ),
    ] = auto_path(),
) -> None:
    """Removes an existing version from an image in the bakery project

    Removes the version subpath and all its contents from the specified image in the bakery project
    and will remove its configuration from the parent image in the bakery.yaml file.
    """
    try:
        c = BakeryConfig.from_context(context)
    except:
        log.exception("Error removing version, could not load bakery project")
        stderr_console.print(f"❌ Failed to remove version '{image_version}' from image '{image_name}'", style="error")
        raise typer.Exit(code=1)

    try:
        c.remove_version(image_name, image_version)
    except:
        log.exception("Error removing version")
        stderr_console.print(f"❌ Failed to remove version '{image_version}' from image '{image_name}'", style="error")
        raise typer.Exit(code=1)

    stderr_console.print(
        f"✅ Successfully removed version '{image_version}' from image '{image_name}'", style="success"
    )
