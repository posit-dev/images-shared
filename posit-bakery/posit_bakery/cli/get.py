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
def images(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
) -> None:
    """Lists all images for the project context."""
    config: BakeryConfig = BakeryConfig.from_context(context)

    # Gather images
    all_images = [image.name for image in config.model.images]
    all_images.sort()

    # Print images
    if all_images:
        for image in all_images:
            stdout_console.print(image)
    else:
        stderr_console.print("No images found matching the specified pattern.", style="warning")


@app.command()
def versions(
    image_name: Annotated[str, typer.Argument(help="The image name or a regex pattern to isolate plan rendering to.")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(help="Include or exclude development versions defined in config."),
    ] = DevVersionInclusionEnum.EXCLUDE,
) -> None:
    """Lists all versions for the given image in the project context."""
    settings = BakerySettings(
        filter=BakeryConfigFilter(image_name=image_name),
        dev_versions=dev_versions,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, settings=settings)

    # Gather versions
    all_versions = set()
    for target in config.targets:
        all_versions.add(target.image_version.name)
    sorted_versions = sorted(all_versions)

    # Print versions
    if sorted_versions:
        for version in sorted_versions:
            stdout_console.print(version)
    else:
        stderr_console.print("No versions found for image.", style="warning")


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
    """Lists all registries for the project context for the given filters."""
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
        for registry in filtered_registries:
            stdout_console.print(registry)
    else:
        stderr_console.print("No registries found matching the specified criteria.", style="warning")
