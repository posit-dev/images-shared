import logging
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakerySettings, BakeryConfigFilter
from posit_bakery.util import auto_path

app = typer.Typer()
log = logging.getLogger(__name__)


@app.command()
def cache_registry(
    registry: Annotated[str, typer.Argument(help="External cache sources")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    untagged: Annotated[Optional[bool], typer.Option(help="Prune dangling caches")] = True,
    older_than: Annotated[Optional[int], typer.Option(help="Prune caches older than specified days")] = None,
    image_name: Annotated[
        Optional[str], typer.Option(help="The image name or a regex pattern to isolate plan rendering to.")
    ] = None,
):
    """Cleans up dangling caches in the specified registry."""
    settings = BakerySettings(filter=BakeryConfigFilter(image_name=image_name))
    config: BakeryConfig = BakeryConfig.from_context(context, settings)

    log.info(f"Cleaning cache registry: {registry}")

    config.clean_caches(registry, remove_untagged=untagged, remove_older_than=timedelta(days=older_than))
