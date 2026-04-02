import logging
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import __make_value_map, with_verbosity_flags
from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakeryConfigFilter
from posit_bakery.log import stderr_console
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True)


class RichHelpPanelEnum(str, Enum):
    """Enum for categorizing options into rich help panels."""

    FILTERS = "Filters"


@app.command()
@with_verbosity_flags
def files(
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
    image_name: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image name to isolate file rendering to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_version: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image version to isolate file rendering to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    template_pattern: Annotated[
        Optional[list[str]],
        typer.Option(
            show_default=False,
            help="Regex pattern(s) to filter which templates to render.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
) -> None:
    """Renders templates to version files matching the given filters

    \b
    This command will rerender each matching image version's files from the templates in the image's template
    directory. Existing configuration details for the version such as dependencies, variants, and the latest flag
    are used and remain unmodified.

    \b
    Existing files will not be removed, but may be overwritten during template rendering.
    """
    _filter = BakeryConfigFilter(
        image_name=image_name,
        image_version=image_version,
    )

    try:
        c = BakeryConfig.from_context(context)
        c.rerender_files(_filter, regex_filters=template_pattern)
    except Exception as e:
        stderr_console.print(e, style="error")
        stderr_console.print(f"❌ Update failed", style="error")
        raise typer.Exit(code=1)

    stderr_console.print(f"✅ Files updated successfully", style="success")


@app.command()
@with_verbosity_flags
def version(
    image_name: Annotated[
        str,
        typer.Argument(
            show_default=False,
            help="The image name to update.",
        ),
    ],
    new_version: Annotated[
        str,
        typer.Argument(
            show_default=False,
            help="The new image version name.",
        ),
    ],
    target_version: Annotated[
        Optional[str],
        typer.Option(
            "--target-version",
            show_default=False,
            help="The existing version name to patch. If not specified, the latest version is used.",
        ),
    ] = None,
    context: Annotated[
        Path,
        typer.Option(help="The root path to use. Defaults to the current working directory where invoked."),
    ] = auto_path(),
    value: Annotated[
        list[str],
        typer.Option(show_default=False, help="A 'key=value' pair to pass to the templates. Accepts multiple pairs."),
    ] = None,
    clean: Annotated[
        Optional[bool],
        typer.Option(help="Remove all existing version files before rendering from templates."),
    ] = True,
) -> None:
    """Update an existing image version with a new version number.

    \b
    Patches the target version with the new version name. If --target-version is not
    specified, the version marked as latest is used. All existing configuration
    (dependencies, OS, latest flag) is preserved.

    \b
    Examples:
      bakery update version connect 2026.03.1
      # Patches the latest version to '2026.03.1'

      bakery update version connect 2026.03.1 --target-version 2026.03.0
      # Explicitly patches '2026.03.0' to '2026.03.1'
    """
    value_map, errors = __make_value_map(value)
    if errors:
        for e in errors:
            log.error(e)
        log.error("❌ Errors parsing key=value pairs")
        raise typer.Exit(code=1)

    try:
        c = BakeryConfig.from_context(context)

        image = c.model.get_image(image_name)
        if image is None:
            raise ValueError(f"Image '{image_name}' does not exist in the config.")

        if target_version:
            old_version_obj = image.get_version(target_version)
            if old_version_obj is None:
                raise ValueError(f"Version '{target_version}' does not exist for image '{image_name}'.")
        else:
            old_version_obj = next((v for v in image.versions if v.latest), None)
            if old_version_obj is None:
                raise ValueError(
                    f"No latest version found for image '{image_name}'. "
                    f"Use --target-version to specify the version to patch."
                )

        old_version_name = old_version_obj.name
        log.info(f"Target version: {old_version_name}")

        c.patch_version(image_name, old_version_name, new_version, values=value_map, clean=clean)
    except Exception as e:
        stderr_console.print(e, style="error")
        stderr_console.print(f"❌ Failed to update version for '{image_name}' to '{new_version}'", style="error")
        raise typer.Exit(code=1)

    stderr_console.print(
        f"✅ Successfully updated '{image_name}' from '{old_version_name}' to '{new_version}'", style="success"
    )
