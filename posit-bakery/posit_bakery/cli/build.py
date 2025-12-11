import logging
import re
from pathlib import Path
from typing import Annotated, Optional

import python_on_whales
import typer

from posit_bakery.cli.common import verbosity_flags, with_temporary_storage
from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum
from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.image import ImageBuildStrategy
from posit_bakery.log import stderr_console, stdout_console
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


@verbosity_flags
@with_temporary_storage
def build(
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
    strategy: Annotated[
        Optional[ImageBuildStrategy],
        typer.Option(
            case_sensitive=False,
            help="The strategy to use when building the image. 'bake' requires Docker Buildkit and builds "
            "images in parallel. 'build' can use generic container builders, such as Podman, and builds "
            "images sequentially.",
            rich_help_panel="Build Configuration & Outputs",
        ),
    ] = ImageBuildStrategy.BAKE,
    fail_fast: Annotated[
        Optional[bool],
        typer.Option(
            "--fail-fast",
            help="Terminate builds on the first failure.",
            rich_help_panel="Build Configuration & Outputs",
        ),
    ] = False,
    plan: Annotated[
        Optional[bool],
        typer.Option("--plan", help="Print the bake plan and exit.", rich_help_panel="Build Configuration & Outputs"),
    ] = False,
    load: Annotated[
        Optional[bool],
        typer.Option(help="Load the image to Docker after building.", rich_help_panel="Build Configuration & Outputs"),
    ] = True,
    push: Annotated[
        Optional[bool],
        typer.Option(
            help="Push the image to its registry tags after building.", rich_help_panel="Build Configuration & Outputs"
        ),
    ] = False,
    clean: Annotated[
        Optional[bool],
        typer.Option(
            help="Clean up intermediary and temporary files after building. Disable for debugging.",
            rich_help_panel="Build Configuration & Outputs",
        ),
    ] = True,
    cache: Annotated[
        Optional[bool],
        typer.Option(help="Enable layer caching for image builds.", rich_help_panel="Build Configuration & Outputs"),
    ] = True,
    cache_registry: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="External registry to use for layer caching.",
            rich_help_panel="Build Configuration & Outputs",
        ),
    ] = None,
    image_name: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image name or a regex pattern to isolate builds to.",
            rich_help_panel="Filters",
        ),
    ] = None,
    image_version: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image version or a regex pattern to isolate builds to.",
            rich_help_panel="Filters",
        ),
    ] = None,
    image_variant: Annotated[
        Optional[str],
        typer.Option(show_default=False, help="The image type to isolate builds to.", rich_help_panel="Filters"),
    ] = None,
    image_os: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image OS name or a regex pattern to isolate builds to.",
            rich_help_panel="Filters",
        ),
    ] = None,
    image_platform: Annotated[
        Optional[list[str]],
        typer.Option(
            show_default=False,
            help="The image platform(s) to isolate builds to, e.g. 'linux/amd64'. "
            "Image build targets incompatible with the given platform(s) will be skipped.",
            rich_help_panel="Filters",
        ),
    ] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(
            help="Include or exclude development version builds defined in config.", rich_help_panel="Filters"
        ),
    ] = DevVersionInclusionEnum.EXCLUDE,
) -> None:
    """Builds images in the context path

    If no options are provided, the command will auto-discover all images in the current
    directory and generate a temporary bake plan to execute for all targets.

    Requires the Docker Engine and CLI to be installed and running for `--strategy bake`.

    Requires Docker, Podman, or nerdctl to be installed and running for `--strategy build`.
    """
    settings = BakerySettings(
        filter=BakeryConfigFilter(
            image_name=image_name,
            image_version=re.escape(image_version) if image_version else None,
            image_variant=image_variant,
            image_os=image_os,
            image_platform=image_platform or [],
        ),
        dev_versions=dev_versions,
        clean_temporary=clean,
        cache_registry=cache_registry,
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

    try:
        config.build_targets(
            load=load,
            push=push,
            cache=cache,
            platforms=image_platform,
            strategy=strategy,
            fail_fast=fail_fast,
        )
    except (python_on_whales.DockerException, BakeryToolRuntimeError):
        stderr_console.print(f"❌ Build failed", style="error")
        raise typer.Exit(code=1)

    stderr_console.print("✅ Build completed", style="success")
