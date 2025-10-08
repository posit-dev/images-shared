from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import __make_value_map
from posit_bakery.config import BakeryConfig
from posit_bakery.log import stderr_console
from posit_bakery.util import auto_path, log

app = typer.Typer(no_args_is_help=True)
update_version = typer.Typer(no_args_is_help=True)
app.add_typer(update_version, name="version", help="Update image versions managed by Posit Bakery")


@update_version.command()
def patch(
    image_name: Annotated[
        str, typer.Argument(help="The image directory to render. This should be the path above the template directory.")
    ],
    old_version: Annotated[str, typer.Argument(help="The existing image version to be patched.")],
    new_version: Annotated[str, typer.Argument(help="The new image version to replace the old version with.")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    value: Annotated[
        list[str], typer.Option(help="A 'key=value' pair to pass to the templates. Accepts multiple pairs.")
    ] = None,
    clean: Annotated[
        Optional[bool],
        typer.Option(help="Remove all existing version files before rendering from templates."),
    ] = True,
) -> None:
    """Patches an existing image version with the given new image version.

    This command will replace the existing old_version in the bakery.yaml file with the new_version, preserving all
    existing configuration details for the version such as dependencies, variants, and the latest flag. Existing files
    for the old_version will be rerendered to reflect the new_version.

    If clean is true, the existing version files for old_version will be removed prior to rendering the new_version
    files.
    """
    value_map = __make_value_map(value)

    try:
        c = BakeryConfig.from_context(context)
        c.patch_version(image_name, old_version, new_version, values=value_map, clean=clean)
    except:
        log.exception("Error patching version")
        stderr_console.print(
            f"❌ Failed to patch version '{image_name}/{old_version}' to '{image_name}/{new_version}'", style="error"
        )
        raise typer.Exit(code=1)

    stderr_console.print(
        f"✅ Successfully patched version '{image_name}/{old_version}' to '{image_name}/{new_version}'", style="success"
    )


@update_version.command()
def files(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_name: Annotated[Optional[str], typer.Option(help="The image name to isolate file rendering to.")] = None,
    image_version: Annotated[
        Optional[str], typer.Option(help="The image version to isolate file rendering to.")
    ] = None,
    template_pattern: Annotated[
        Optional[list[str]],
        typer.Option(help="A glob pattern to filter which templates to render. Uses regex syntax."),
    ] = None,
    clean: Annotated[
        Optional[bool],
        typer.Option(help="Remove all existing matching files before rendering from templates."),
    ] = True,
) -> None:
    """Rerenders versions from templates matching the given filters.

    This command will rerender each matching image version's files from the templates in the image's template
    directory. Existing configuration details for the version such as dependencies, variants, and the latest flag
    are used and remain unmodified.

    If clean is true, the existing version files will be removed prior to rendering.
    """
