import logging
from pathlib import Path
import re
from typing import Annotated, Optional

import typer

from posit_bakery.config.config import BakerySettings, BakeryConfigFilter, BakeryConfig
from posit_bakery.const import DevVersionInclusionEnum
from posit_bakery.log import stderr_console, stdout_console
from posit_bakery.util import auto_path

app = typer.Typer(no_args_is_help=True)
log = logging.getLogger(__name__)


@app.command()
def registries(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_name: Annotated[
        Optional[str], typer.Option(help="The image name or a regex pattern to isolate plan rendering to.")
    ] = None,
    image_version: Annotated[
        Optional[str], typer.Option(help="The image version or a regex pattern to isolate plan rendering to.")
    ] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(help="Include or exclude development versions defined in config."),
    ] = DevVersionInclusionEnum.EXCLUDE,
    pattern: Annotated[Optional[str], typer.Option(help="A regex pattern to filter registries listed.")] = None,
) -> None:
    """Lists all registries for the current project."""
    settings = BakerySettings(
        filter=BakeryConfigFilter(
            image_name=image_name,
            image_version=image_version,
        ),
        dev_versions=dev_versions,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, settings=settings)

    # Gather registries
    all_registries = set()
    for target in config.targets:
        target_tags = [tag.split(":")[0] for tag in target.tags]
        all_registries.update(target_tags)

    # Apply pattern filter
    if pattern:
        regex = re.compile(pattern)
        filtered_registries = [reg for reg in all_registries if regex.search(reg)]
    else:
        filtered_registries = list(all_registries)
    filtered_registries.sort()

    # Print registries
    if filtered_registries:
        for registry in sorted(filtered_registries):
            stdout_console.print(registry)
    else:
        stderr_console.print("No registries found matching the specified criteria.", style="warning")
