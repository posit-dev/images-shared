import logging
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import python_on_whales
import typer

from posit_bakery.cli.common import with_verbosity_flags, with_temporary_storage
from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakeryConfigFilter, BakerySettings
from posit_bakery.config.image.dev_version.spec import DevBuildSpec
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.error import BakeryBuildErrorGroup, BakeryToolRuntimeError
from posit_bakery.image import ImageBuildStrategy
from posit_bakery.log import stderr_console, stdout_console
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


def _parse_dev_spec(ctx: typer.Context, param: typer.CallbackParam, value: str | None) -> DevBuildSpec | None:
    if value is None:
        return None
    from pydantic import ValidationError

    try:
        return DevBuildSpec.model_validate_json(value)
    except ValidationError as e:
        raise typer.BadParameter(str(e), ctx=ctx, param=param) from e


class RichHelpPanelEnum(str, Enum):
    """Enum for categorizing options into rich help panels."""

    BUILD_CONFIGURATION_AND_OUTPUTS = "Build Configuration & Outputs"
    FILTERS = "Filters"


@with_verbosity_flags
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
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = ImageBuildStrategy.BAKE,
    fail_fast: Annotated[
        Optional[bool],
        typer.Option(
            "--fail-fast",
            help="Terminate builds on the first failure.",
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = False,
    retry: Annotated[
        int,
        typer.Option(
            min=0,
            help="Number of times to retry a failed build.",
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = 0,
    plan: Annotated[
        Optional[bool],
        typer.Option(
            "--plan",
            help="Print the bake plan and exit.",
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = False,
    load: Annotated[
        Optional[bool],
        typer.Option(
            help="Load the image to Docker after building.",
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = True,
    push: Annotated[
        Optional[bool],
        typer.Option(
            help="Push the image to its registry tags after building.",
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = False,
    clean: Annotated[
        Optional[bool],
        typer.Option(
            help="Clean up intermediary and temporary files after building. Disable for debugging.",
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = True,
    metadata_file: Annotated[
        Optional[Path],
        typer.Option(
            writable=True,
            resolve_path=True,
            help="The path to write JSON build metadata to once builds are finished.",
            rich_help_panel="Build Configuration & Outputs",
        ),
    ] = None,
    pull: Annotated[
        Optional[bool],
        typer.Option(
            help="Always pull the latest version of base images.",
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = False,
    cache: Annotated[
        Optional[bool],
        typer.Option(
            help="Enable layer caching for image builds.",
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = True,
    cache_registry: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="External registry to use for layer caching.",
            rich_help_panel=RichHelpPanelEnum.BUILD_CONFIGURATION_AND_OUTPUTS,
        ),
    ] = None,
    temp_registry: Annotated[
        Optional[str],
        typer.Option(
            help="Temporary registry to use for multiplatform split/merge builds.",
            rich_help_panel="Build Configuration & Outputs",
        ),
    ] = None,
    image_name: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image name or a regex pattern to isolate builds to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_version: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image version or version prefix to isolate builds to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_variant: Annotated[
        Optional[str],
        typer.Option(
            show_default=False, help="The image type to isolate builds to.", rich_help_panel=RichHelpPanelEnum.FILTERS
        ),
    ] = None,
    image_os: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image OS name or a regex pattern to isolate builds to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    image_platform: Annotated[
        Optional[list[str]],
        typer.Option(
            show_default=False,
            help="The image platform(s) to isolate builds to, e.g. 'linux/amd64'. "
            "Image build targets incompatible with the given platform(s) will be skipped.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(
            help="Include or exclude development version builds defined in config.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = DevVersionInclusionEnum.EXCLUDE,
    dev_channel: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-channel",
            help="Filter development versions to a specific release channel.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    dev_stream: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-stream",
            help="Deprecated: use --dev-channel instead.",
            hidden=True,
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    matrix_versions: Annotated[
        Optional[MatrixVersionInclusionEnum],
        typer.Option(
            help="Include or exclude versions defined in image matrix.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = MatrixVersionInclusionEnum.EXCLUDE,
    latest: Annotated[
        Optional[bool],
        typer.Option(
            "--latest",
            help="Build only the latest version of each image. Development versions are ignored by this filter.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = False,
    dev_spec: Annotated[
        Optional[str],
        typer.Option(
            "--dev-spec",
            envvar="BAKERY_DEV_SPEC",
            help='JSON spec for a dispatched dev build. Ex: \'{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}\'',
            rich_help_panel=RichHelpPanelEnum.FILTERS,
            callback=_parse_dev_spec,
        ),
    ] = None,
) -> None:
    """Builds images in the context path

    If no options are provided, the command will auto-discover all images in the current
    directory and generate a temporary bake plan to execute for all targets.

    Requires the Docker Engine and CLI to be installed and running for `--strategy bake`.

    Requires Docker, Podman, or nerdctl to be installed and running for `--strategy build`.
    """
    if dev_stream is not None:
        log.warning("--dev-stream is deprecated, use --dev-channel instead.")
        if dev_channel is None:
            dev_channel = dev_stream
    settings = BakerySettings(
        filter=BakeryConfigFilter(
            image_name=image_name,
            image_version=image_version,
            image_variant=image_variant,
            image_os=image_os,
            image_platform=image_platform or [],
        ),
        dev_versions=dev_versions,
        dev_channel=dev_channel,
        matrix_versions=matrix_versions,
        latest=latest,
        clean_temporary=clean,
        cache_registry=cache_registry,
        temp_registry=temp_registry,
        dev_spec=dev_spec,  # type: ignore[arg-type]
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
        stdout_console.print_json(config.bake_plan_targets(push=push))
        raise typer.Exit(code=0)

    try:
        config.build_targets(
            load=load,
            push=push,
            pull=pull,
            cache=cache,
            platforms=image_platform,
            strategy=strategy,
            fail_fast=fail_fast,
            retry=retry,
            metadata_file=metadata_file,
        )
    except BakeryBuildErrorGroup as e:
        stderr_console.print(str(e))
        stderr_console.print("❌ Build failed", style="error")
        raise typer.Exit(code=1)
    except (python_on_whales.DockerException, BakeryToolRuntimeError):
        stderr_console.print("❌ Build failed", style="error")
        raise typer.Exit(code=1)

    stderr_console.print("✅ Build completed", style="success")
