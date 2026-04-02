import json
import logging
import re
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags
from posit_bakery.config.config import BakerySettings, BakeryConfigFilter, BakeryConfig
from posit_bakery.const import DevVersionInclusionEnum, GetTagsOutputFormat, MatrixVersionInclusionEnum
from posit_bakery.log import stderr_console, stdout_console
from posit_bakery.util import auto_path

app = typer.Typer(no_args_is_help=True)
log = logging.getLogger(__name__)


def _format_component_output(targets: list) -> dict:
    """Format tags output grouped by image components (name/version/variant/os)."""
    data = {}
    for target in targets:
        image = target.image_name
        version = target.image_version.name
        tag_list = target.tags.as_strings()

        image_node = data.setdefault(image, {})

        if target.image_variant is None and target.image_os is None:
            # No variant, no OS: tags directly under version
            image_node.setdefault(version, []).extend(tag_list)
        elif target.image_variant is None:
            # No variant, has OS: tags under version -> os_name
            version_node = image_node.setdefault(version, {})
            version_node.setdefault(target.image_os.name, []).extend(tag_list)
        elif target.image_os is None:
            # Has variant, no OS: tags under version -> variant_name
            version_node = image_node.setdefault(version, {})
            version_node.setdefault(target.image_variant.name, []).extend(tag_list)
        else:
            # Has both variant and OS: full nesting
            version_node = image_node.setdefault(version, {})
            variant_node = version_node.setdefault(target.image_variant.name, {})
            variant_node.setdefault(target.image_os.name, []).extend(tag_list)

    return data


def _format_uid_output(targets: list) -> dict:
    """Format tags output keyed by target uid."""
    return {target.uid: target.tags.as_strings() for target in targets}


@app.command()
@with_verbosity_flags
def tags(
    image_name: Annotated[str | None, typer.Option(help="The image name to isolate tags to.")] = None,
    image_version: Annotated[str | None, typer.Option(help="The image version to isolate tags to.")] = None,
    image_variant: Annotated[str | None, typer.Option(help="The image variant to isolate tags to.")] = None,
    image_os: Annotated[str | None, typer.Option(help="The image OS to isolate tags to.")] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(
            help="Include development versions defined in config.",
            rich_help_panel="Filters",
        ),
    ] = DevVersionInclusionEnum.EXCLUDE,
    matrix_versions: Annotated[
        Optional[MatrixVersionInclusionEnum],
        typer.Option(
            help="Include versions defined in image matrix.",
            rich_help_panel="Filters",
        ),
    ] = MatrixVersionInclusionEnum.EXCLUDE,
    output: Annotated[
        Optional[GetTagsOutputFormat],
        typer.Option(
            help="Output format for tags.",
            rich_help_panel="Output",
        ),
    ] = GetTagsOutputFormat.COMPONENT,
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
):
    """Get the list of tags that would be built for the given context and filters."""
    try:
        settings = BakerySettings(
            filter=BakeryConfigFilter(
                image_name=image_name,
                image_version=re.escape(image_version) if image_version else None,
                image_variant=image_variant,
                image_os=image_os,
            ),
            dev_versions=dev_versions,
            matrix_versions=matrix_versions,
        )
        config: BakeryConfig = BakeryConfig.from_context(context, settings)

        if output == GetTagsOutputFormat.UID:
            data = _format_uid_output(config.targets)
        else:
            data = _format_component_output(config.targets)

        stdout_console.print(json.dumps(data, indent=2))

    except:
        log.exception("Failed to load bakery config")
        raise typer.Exit(code=1)


@app.command()
@with_verbosity_flags
def version(
    image_name: Annotated[
        str,
        typer.Argument(
            show_default=False,
            help="The image name to query.",
        ),
    ],
    subpath: Annotated[
        Optional[str],
        typer.Option(
            "--subpath",
            show_default=False,
            help="Find the version with this subpath.",
        ),
    ] = None,
    latest: Annotated[
        bool,
        typer.Option(
            "--latest",
            help="Find the version marked as latest. This is the default when no other filter is given.",
        ),
    ] = False,
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
    """Get a version name from bakery.yaml.

    \b
    Returns the latest version by default. Use --subpath to find a version by its
    configured subpath instead.

    \b
    Examples:
      bakery get version connect                    Find the latest version
      bakery get version connect --latest           Same as above (explicit)
      bakery get version connect --subpath 2026.03  Find version with subpath '2026.03'
    """
    if latest and subpath:
        stderr_console.print("Cannot specify both --subpath and --latest.", style="error")
        raise typer.Exit(code=1)

    # Default to latest when no filter is given.
    if not subpath:
        latest = True

    try:
        config = BakeryConfig.from_context(context)
        image = config.model.get_image(image_name)
        if image is None:
            stderr_console.print(f"Image '{image_name}' does not exist in the config.", style="error")
            raise typer.Exit(code=1)

        if latest:
            for v in image.versions:
                if v.latest:
                    stdout_console.print(v.name, highlight=False)
                    return
            stderr_console.print(f"No latest version found for image '{image_name}'.", style="error")
            raise typer.Exit(code=1)

        found = image.get_version_by_subpath(subpath)
        if found is None:
            stderr_console.print(
                f"No version found with subpath '{subpath}' for image '{image_name}'.",
                style="error",
            )
            raise typer.Exit(code=1)

        stdout_console.print(found.name, highlight=False)

    except typer.Exit:
        raise
    except Exception as e:
        stderr_console.print(str(e), style="error")
        raise typer.Exit(code=1)
