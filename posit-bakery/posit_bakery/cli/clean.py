import logging
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags
from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakerySettings, BakeryConfigFilter
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
    settings = BakerySettings(filter=BakeryConfigFilter(image_name=image_name))
    config: BakeryConfig = BakeryConfig.from_context(context, settings)

    log.info(f"Cleaning cache registry: {registry}")

    config.clean_caches(
        registry,
        remove_untagged=untagged,
        remove_older_than=timedelta(days=older_than) if older_than else None,
        dry_run=dry_run,
    )
