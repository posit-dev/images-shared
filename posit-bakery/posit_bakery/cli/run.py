import logging
import re
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum
from posit_bakery.log import stderr_console
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True)


@app.command()
def dgoss(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_name: Annotated[Optional[str], typer.Option(help="The image name to isolate goss testing to.")] = None,
    image_version: Annotated[Optional[str], typer.Option(help="The image version to isolate goss testing to.")] = None,
    image_variant: Annotated[Optional[str], typer.Option(help="The image type to isolate goss testing to.")] = None,
    image_os: Annotated[Optional[str], typer.Option(help="The image OS to isolate goss testing to.")] = None,
    platform: Annotated[
        Optional[list[str]], typer.Option(help="The image platform to isolate goss testing to.")
    ] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(help="Include or exclude development versions defined in config."),
    ] = DevVersionInclusionEnum.EXCLUDE,
    metadata_file: Annotated[
        Optional[Path],
        typer.Option(
            help="Path to a build metadata file. If given, attempts to run tests against image artifacts in the file."
        ),
    ] = None,
    clean: Annotated[
        Optional[bool],
        typer.Option(help="Clean up intermediary and temporary files after building. Can be helpful for debugging."),
    ] = True,
) -> None:
    """Runs dgoss tests against images in the context path

    If no options are provided, the command will auto-discover all images in the current
    directory and generate and execute test commands on all images.

    Images are expected to be available to the local Docker daemon. It is advised to run `build` before running
    dgoss tests. If a metadata file is provided, images will be pulled and tested based on the artifacts in the file.

    Requires goss and dgoss to be installed on the system. Paths to the binaries can be set with the `GOSS_BIN` and
    `DGOSS_BIN` environment variables if not present in the system PATH.
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
        metadata_file=metadata_file,
    )
    c = BakeryConfig.from_context(context, settings)

    if metadata_file:
        log.info(f"Using build metadata from {metadata_file} to locate images for dgoss testing.")
        c.attach_metadata_to_targets(pull=True)

    results, err = c.dgoss_targets()

    stderr_console.print(results.table())
    if results.test_failures:
        stderr_console.print("-" * 80)
        for uid, failures in results.test_failures.items():
            stderr_console.print(f"{uid} test failures:", style="error")
            for failed_result in failures:
                stderr_console.print(f"  - {failed_result.summary_line_compact}", style="error")
        stderr_console.print(f"❌ dgoss test(s) failed", style="error")
    if err:
        stderr_console.print("-" * 80)
        stderr_console.print(err, style="error")
        stderr_console.print(f"❌ dgoss command(s) failed to execute", style="error")
    if results.test_failures or err:
        raise typer.Exit(code=1)

    stderr_console.print(f"✅ Tests completed", style="success")
