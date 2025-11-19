import json
import logging
import re
from pathlib import Path
from typing import Annotated, Optional

import python_on_whales
import typer

from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum
from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.image import ImageBuildStrategy
from posit_bakery.log import stderr_console, stdout_console
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


def build(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    strategy: Annotated[
        Optional[ImageBuildStrategy],
        typer.Option(
            help="The strategy to use when building the image. 'bake' requires Docker Buildkit and builds "
            "images in parallel. 'build' can use generic container builders, such as Podman, and builds "
            "images sequentially."
        ),
    ] = ImageBuildStrategy.BAKE,
    image_name: Annotated[
        Optional[str], typer.Option(help="The image name or a regex pattern to isolate plan rendering to.")
    ] = None,
    image_version: Annotated[
        Optional[str], typer.Option(help="The image version or a regex pattern to isolate plan rendering to.")
    ] = None,
    image_variant: Annotated[Optional[str], typer.Option(help="The image type to isolate plan rendering to.")] = None,
    image_os: Annotated[
        Optional[str], typer.Option(help="The image OS to build as an OS name or a regex pattern.")
    ] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(help="Include or exclude development versions defined in config."),
    ] = DevVersionInclusionEnum.EXCLUDE,
    clean: Annotated[
        Optional[bool],
        typer.Option(help="Clean up intermediary and temporary files after building. Can be helpful for debugging."),
    ] = True,
    plan: Annotated[Optional[bool], typer.Option(help="Print the bake plan and exit.")] = False,
    load: Annotated[Optional[bool], typer.Option(help="Load the image to Docker after building.")] = True,
    push: Annotated[Optional[bool], typer.Option(help="Push the image to the registry after building.")] = False,
    platform: Annotated[
        Optional[list[str]],
        typer.Option(help="Isolate builds to images compatible with the given platform (e.g., linux/amd64)."),
    ] = None,
    cache: Annotated[Optional[bool], typer.Option(help="Enable caching for image builds.")] = True,
    cache_registry: Annotated[Optional[str], typer.Option(help="External cache sources")] = None,
    temp_registry: Annotated[
        Optional[str], typer.Option(help="Temporary registry to use for multiplatform split/merge builds.")
    ] = None,
    metadata_file: Annotated[
        Optional[Path],
        typer.Option(help="The path to write JSON build metadata to once builds are finished."),
    ] = None,
    fail_fast: Annotated[Optional[bool], typer.Option(help="Stop building on the first failure.")] = False,
) -> None:
    """Builds images in the context path

    If no options are provided, the command will auto-discover all images in the current
    directory and generate a temporary bake plan to execute for all targets.

    Requires the Docker Engine and CLI to be installed and running for `--strategy bake`.

    Requires Docker, Podman, or nerdctl to be installed and running for `--strategy build`.
    """
    if platform is None:
        platform = []

    settings = BakerySettings(
        filter=BakeryConfigFilter(
            image_name=image_name,
            image_version=re.escape(image_version) if image_version else None,
            image_variant=image_variant,
            image_os=image_os,
            image_platform=platform,
        ),
        dev_versions=dev_versions,
        clean_temporary=clean,
        cache_registry=cache_registry,
        temp_registry=temp_registry,
        metadata_file=metadata_file,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, settings)

    if plan:
        if strategy == ImageBuildStrategy.BUILD:
            # TODO: This should turn into dry-run behavior eventually.
            stderr_console.print(
                "❌ The --plan option is not supported with the 'build' strategy. "
                "Please use the 'bake' strategy to print the bake plan.",
                style="error",
            )
            raise typer.Exit(code=1)
        stdout_console.print_json(config.bake_plan_targets())
        raise typer.Exit(code=0)
    if metadata_file and strategy == ImageBuildStrategy.BAKE:
        stderr_console.print(
            "⚠️ Warning: The --metadata-file option is not yet supported with the 'bake' strategy. "
            "No metadata will be written.",
            style="warning",
        )

    try:
        config.build_targets(
            load=load,
            push=push,
            cache=cache,
            platforms=platform,
            strategy=strategy,
            fail_fast=fail_fast,
        )
    except (python_on_whales.DockerException, BakeryToolRuntimeError):
        stderr_console.print(f"❌ Build failed", style="error")
        raise typer.Exit(code=1)

    stderr_console.print("✅ Build completed", style="success")
