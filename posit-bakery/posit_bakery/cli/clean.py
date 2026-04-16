import logging
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags
from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakerySettings, BakeryConfigFilter
from posit_bakery.config.image.posit_product.const import ReleaseStreamEnum
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.util import auto_path

app = typer.Typer()
log = logging.getLogger(__name__)


class RichHelpPanelEnum(str, Enum):
    """Enum for categorizing options into rich help panels."""

    FILTERS = "Filters"


@app.command()
@with_verbosity_flags
def cache_registry(
    registry: Annotated[
        str, typer.Argument(show_default=False, help="GHCR registry to clean caches in *(ex. ghcr.io/my-org)*.")
    ],
    context: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
            help="The root path to use. Defaults to the current working directory where invoked.",
        ),
    ] = auto_path(),
    untagged: Annotated[
        Optional[bool], typer.Option(help="Prune dangling caches.", rich_help_panel=RichHelpPanelEnum.FILTERS)
    ] = True,
    older_than: Annotated[
        Optional[int],
        typer.Option(
            show_default=False,
            help="Prune caches older than specified days.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_name: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image name or a regex pattern to isolate clean operations to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(
            help="Include or exclude development version caches.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = DevVersionInclusionEnum.EXCLUDE,
    dev_stream: Annotated[
        Optional[ReleaseStreamEnum],
        typer.Option(
            help="Filter development versions to a specific release stream.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    matrix_versions: Annotated[
        Optional[MatrixVersionInclusionEnum],
        typer.Option(
            help="Include or exclude matrix version caches.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = MatrixVersionInclusionEnum.EXCLUDE,
    dry_run: Annotated[
        Optional[bool], typer.Option("--dry-run", help="If set, print what would be deleted and exit.")
    ] = False,
):
    """Cleans up dangling caches in an external registry

    \b
    ⚠️ **This command currently only supports GHCR registries.** ⚠️

    This command is intended to be used as a cleanup utility for build caches created with the
    `bakery build --cache-registry <registry>` option. By default, it will remove all untagged/dangling caches.
    Additional filters can be applied to remove caches older than a specified number of days. Caches are assumed to be
    created by Bakery in the registry namespace `<registry>/<image-name>/cache`. If the `--image-name` filter is not
    provided, all image caches for the project will be cleaned.
    """
    settings = BakerySettings(
        filter=BakeryConfigFilter(image_name=image_name),
        cache_registry=registry,
        dev_versions=dev_versions,
        dev_stream=dev_stream,
        matrix_versions=matrix_versions,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, settings)

    log.info(f"Cleaning cache registries in {registry}")

    errors = config.clean_caches(
        remove_untagged=untagged,
        remove_older_than=timedelta(days=older_than) if older_than else None,
        dry_run=dry_run,
    )
    if errors:
        log.error(f"Completed with {len(errors)} errors encountered during cleanup.")
        raise typer.Exit(code=1)


@app.command()
@with_verbosity_flags
def temp_registry(
    registry: Annotated[
        str,
        typer.Argument(show_default=False, help="GHCR registry to clean temporary images in *(ex. ghcr.io/my-org)*."),
    ],
    context: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
            help="The root path to use. Defaults to the current working directory where invoked.",
        ),
    ] = auto_path(),
    untagged: Annotated[
        Optional[bool], typer.Option(help="Prune dangling images.", rich_help_panel=RichHelpPanelEnum.FILTERS)
    ] = False,
    older_than: Annotated[
        Optional[int],
        typer.Option(
            show_default=False,
            help="Prune caches older than specified days.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_name: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image name or a regex pattern to isolate clean operations to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(
            help="Include or exclude development version temporary images.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = DevVersionInclusionEnum.EXCLUDE,
    dev_stream: Annotated[
        Optional[ReleaseStreamEnum],
        typer.Option(
            help="Filter development versions to a specific release stream.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    matrix_versions: Annotated[
        Optional[MatrixVersionInclusionEnum],
        typer.Option(
            help="Include or exclude matrix version temporary images.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = MatrixVersionInclusionEnum.EXCLUDE,
    dry_run: Annotated[
        Optional[bool], typer.Option("--dry-run", help="If set, print what would be deleted and exit.")
    ] = False,
):
    """Cleans up temporary images in an external registry

    \b
    ⚠️ **This command currently only supports GHCR registries.** ⚠️

    This command is intended to be used as a cleanup utility for temporary images created with the
    `bakery build --temp-registry <registry>` option. By default, it will remove all images older than 3 days.
    Images are assumed to be created by Bakery in the registry namespace `<registry>/<image-name>/tmp`. If the
    `--image-name` filter is not provided, all images for the project will be cleaned.
    """
    settings = BakerySettings(
        filter=BakeryConfigFilter(image_name=image_name),
        temp_registry=registry,
        dev_versions=dev_versions,
        dev_stream=dev_stream,
        matrix_versions=matrix_versions,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, settings)

    log.info(f"Cleaning temporary registries in {registry}")

    errors = config.clean_temporary(
        remove_untagged=untagged,
        remove_older_than=timedelta(days=older_than) if older_than else None,
        dry_run=dry_run,
    )
    if errors:
        log.error(f"Completed with {len(errors)} errors encountered during cleanup.")
        raise typer.Exit(code=1)
