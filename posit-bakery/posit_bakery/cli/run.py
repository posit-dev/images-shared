import logging
from pathlib import Path
from typing import Annotated, List, Optional

import typer

from posit_bakery import error
from posit_bakery.cli.common import _wrap_project_load
from posit_bakery.error import BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup
from posit_bakery.log import stderr_console
from posit_bakery.models.manifest.snyk import SnykContainerSubcommand
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True)


@app.command()
def dgoss(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_name: Annotated[str, typer.Option(help="The image name to isolate goss testing to.")] = None,
    image_version: Annotated[str, typer.Option(help="The image version to isolate goss testing to.")] = None,
    image_type: Annotated[Optional[str], typer.Option(help="The image type to isolate plan rendering to.")] = None,
    run_option: Annotated[
        List[str], typer.Option(
            "--run-opt", help="Additional runtime options to pass to dgoss. Multiple can be provided."
        )
    ] = None,
) -> None:
    """Runs dgoss tests against images in the context path

    If no options are provided, the command will auto-discover all images in the current
    directory and generate and execute test commands on all images.

    Images are expected to be in the local Docker daemon. It is advised to run `build --load` before running
    dgoss tests.

    Requires goss and dgoss to be installed on the system. Paths to the binaries can be set with the `GOSS_BIN` and
    `DGOSS_BIN` environment variables if not present in the system PATH.
    """
    # TODO: add skip_override back in
    p = _wrap_project_load(context)

    try:
        p.dgoss(image_name, image_version, image_type, run_option)
    except (BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup) as e:
        stderr_console.print("-" * 80)
        stderr_console.print(e, style="error")
        stderr_console.print(f"❌ dgoss tests failed", style="error")
        raise typer.Exit(code=1)

    stderr_console.print(f"✅ Tests completed", style="success")


@app.command()
def snyk(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    subcommand: Annotated[
        SnykContainerSubcommand, typer.Argument(help="The `snyk container` subcommand to run.")
    ] = SnykContainerSubcommand.test,
    image_name: Annotated[str, typer.Option(help="The image name to isolate snyk testing to.")] = None,
    image_version: Annotated[str, typer.Option(help="The image version to isolate snyk testing to.")] = None,
) -> None:
    """Runs a Snyk CLI command against images in the project

    If no options are provided, the command will auto-discover all images in the current
    directory and generate and execute `snyk container test` commands on all images.

    Images are expected to be in the local image cache. It is advised to run `build --load` before running
    Snyk commands.

    Requires snyk to be installed on the system. Paths to the binaries can be set with the `SNYK_BIN` environment
    variable if not present in the system PATH.

    For more information on the `snyk container` subcommands, see Snyk's documentation:
    https://docs.snyk.io/snyk-cli/scan-and-maintain-projects-using-the-cli/snyk-cli-for-snyk-container
    """
    # TODO: add skip_override back in
    p = _wrap_project_load(context)

    try:
        p.snyk(subcommand, image_name=image_name, image_version=image_version)
    except (BakeryToolRuntimeError, BakeryToolRuntimeErrorGroup) as e:
        stderr_console.print("-" * 80)
        stderr_console.print(e, style="error")
        stderr_console.print(f"❌ snyk container {subcommand.value} command(s) failed", style="error")
        raise typer.Exit(code=1)

    stderr_console.print(f"✅ snyk container {subcommand.value} command(s) completed", style="success")
