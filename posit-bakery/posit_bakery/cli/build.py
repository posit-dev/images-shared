import logging
from pathlib import Path
from typing import Annotated, Optional

from python_on_whales.exceptions import DockerException
import typer

from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakeryConfigFilter
from posit_bakery.image import ImageBuildStrategy
from posit_bakery.log import stderr_console
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
    plan: Annotated[Optional[bool], typer.Option("--plan", help="Print the bake plan and exit.")] = False,
    load: Annotated[Optional[bool], typer.Option(help="Load the image to Docker after building.")] = True,
    push: Annotated[Optional[bool], typer.Option(help="Push the image to the registry after building.")] = False,
    no_cache: Annotated[Optional[bool], typer.Option(help="Disable caching for build.")] = False,
    fail_fast: Annotated[Optional[bool], typer.Option(help="Stop building on the first failure.")] = False,
) -> None:
    """Builds images in the context path using buildx bake

    If no options are provided, the command will auto-discover all images in the current
    directory and generate a temporary bake plan to execute for all targets.

    Requires the Docker Engine and CLI to be installed and running.
    """
    _filter: BakeryConfigFilter = BakeryConfigFilter(
        image_name=image_name,
        image_version=image_version,
        image_variant=image_variant,
        image_os=image_os,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, _filter)

    if plan:
        if strategy == ImageBuildStrategy.BUILD:
            # TODO: This should turn into dry-run behavior eventually.
            stderr_console.print(
                "❌ The --plan option is not supported with the 'build' strategy. "
                "Please use the 'bake' strategy to print the bake plan.",
                style="error",
            )
            raise typer.Exit(code=1)
        stderr_console.print_json(config.bake_plan_targets())

    try:
        config.build_targets(load=load, push=push, cache=not no_cache, strategy=strategy, fail_fast=fail_fast)
    except DockerException as e:
        stderr_console.print(f"❌ Build failed with exit code {e.return_code}", style="error")
        raise typer.Exit(code=1)

    stderr_console.print("✅ Build completed", style="success")
