import logging
from pathlib import Path
from typing import Annotated, List, Optional

import typer

from posit_bakery import error
from posit_bakery.cli.common import __make_value_map
from posit_bakery.config import BakeryConfig
from posit_bakery.const import DEFAULT_BASE_IMAGE
from posit_bakery.log import stderr_console
from posit_bakery.util import auto_path

app = typer.Typer(no_args_is_help=True)
log = logging.getLogger(__name__)


@app.command()
def project(
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
    """Creates a new project in the context path

    This tool will create a new directory in the context path with the following structure:

    \b
    ```
    .
    └── context/
        └── bakery.yaml.
    ```
    """
    try:
        BakeryConfig.from_context(context)
        stderr_console.print(f"Project already exists in '{context}'", style="info")
        raise typer.Exit(code=1)
    except error.BakeryFileError:
        log.info(f"No project found, creating a new project in '{context}'")
        BakeryConfig.new(context)
        stderr_console.print(f"✅ Project initialized in '{context}'", style="success")


@app.command()
def image(
    image_name: Annotated[str, typer.Argument(show_default=False, help="The image name to create a skeleton for.")],
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
    base_image: Annotated[
        str, typer.Option(help="The base to use for the new image.", rich_help_panel="Image Configuration")
    ] = DEFAULT_BASE_IMAGE,
    subpath: Annotated[
        Optional[str],
        typer.Option(
            show_default="based on image_name",
            help="The directory name to use for the image.",
            rich_help_panel="Image Configuration",
        ),
    ] = None,
    display_name: Annotated[
        Optional[str],
        typer.Option(
            show_default="based on image_name",
            help="The display name for the image.",
            rich_help_panel="Image Configuration",
        ),
    ] = None,
    description: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The description for the image. Used in labels.",
            rich_help_panel="Image Configuration",
        ),
    ] = None,
    documentation_url: Annotated[
        Optional[str],
        typer.Option(
            show_default=False, help="The documentation URL for the image.", rich_help_panel="Image Configuration"
        ),
    ] = None,
) -> None:
    """Creates a quickstart skeleton for a new image in the context path

    This tool will create a new directory in the context path with the following structure:

    \b
    ```
    .
    └── image_name/
        └── template/
            ├── deps/
            │   └── packages.txt.jinja2
            ├── test/
            │   └── goss.yaml.jinja2
            └── Containerfile.jinja2
    ```
    """
    try:
        c = BakeryConfig.from_context(context)
        c.create_image(
            image_name,
            base_image=base_image,
            subpath=subpath,
            display_name=display_name,
            description=description,
            documentation_url=documentation_url,
        )
    except:
        log.exception("Error creating image")
        stderr_console.print(f"❌ Failed to create image '{image_name}'", style="error")
        raise typer.Exit(code=1)

    stderr_console.print(f"✅ Successfully created image '{image_name}'", style="success")


@app.command()
def version(
    image_name: Annotated[
        str,
        typer.Argument(
            show_default=False,
            help="The image to which the version belongs. This must match an image name present in the bakery.yaml "
            "configuration.",
        ),
    ],
    image_version: Annotated[
        str, typer.Argument(show_default=False, help="The new version to render the templates to.")
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
    subpath: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The subdirectory to use for the version. Defaults to the image version.",
            rich_help_panel="Version Configuration",
        ),
    ] = None,
    value: Annotated[
        List[str],
        typer.Option(
            show_default=False,
            help="A 'key=value' pair to pass to the templates. Accepts multiple pairs.",
            rich_help_panel="Version Configuration",
        ),
    ] = None,
    mark_latest: Annotated[
        bool,
        typer.Option(help="Skip marking the latest version of the image.", rich_help_panel="Version Configuration"),
    ] = True,
    force: Annotated[
        Optional[bool], typer.Option("--force", help="Force overwrite of existing version directory.")
    ] = False,
) -> None:
    """Renders templates for an image to a versioned subdirectory of the image directory.

    This tool expects an image directory to use the following structure as generated by `bakery create image`:

    \b
    ```
    .
    └── image_path/
        └── template/
            ├── optional_subdirectories/
            │   └── *.jinja2
            ├── *.jinja2
            └── Containerfile*.jinja2
    ```
    """

    value_map = __make_value_map(value)

    try:
        c = BakeryConfig.from_context(context)
        c.create_version(
            image_name=image_name,
            subpath=subpath,
            version=image_version,
            values=value_map,
            latest=mark_latest,
            force=force,
        )
    except:
        log.exception("Error creating version")
        stderr_console.print(f"❌ Failed to create version '{image_name}/{image_version}'", style="error")
        raise typer.Exit(code=1)

    stderr_console.print(f"✅ Successfully created version '{image_name}/{image_version}'", style="success")
