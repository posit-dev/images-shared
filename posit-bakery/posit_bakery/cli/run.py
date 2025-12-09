import logging
import platform
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
    image_platform: Annotated[
        Optional[str],
        typer.Option(
            help="Filters which image build platform to run tests for, e.g. 'linux/amd64'. Image test targets "
            "incompatible with the given platform(s) will be skipped. Requires a compatible goss binary. If not "
            "provided, the host architecture will be used by default.",
        ),
    ] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(help="Include or exclude development versions defined in config."),
    ] = DevVersionInclusionEnum.EXCLUDE,
    clean: Annotated[
        Optional[bool],
        typer.Option(help="Clean up intermediary and temporary files after building. Can be helpful for debugging."),
    ] = True,
) -> None:
    """Runs dgoss tests against images in the context path

    If no options are provided, the command will auto-discover all images in the current
    directory and generate and execute test commands on all images.

    Images are expected to be available to the local Docker daemon. It is advised to run `build` before running
    dgoss tests.

    Requires goss and dgoss to be installed on the system. Paths to the binaries can be set with the `GOSS_BIN` and
    `DGOSS_BIN` environment variables if not present in the system PATH.
    """
    # Autoselect host arhitecture platform if not specified.
    if image_platform is None:
        machine = platform.machine()
        arch_map = {
            "x86_64": "amd64",
            "aarch64": "arm64",
        }
        arch = arch_map.get(machine, "amd64")
        image_platform = f"linux/{arch}"

    settings = BakerySettings(
        filter=BakeryConfigFilter(
            image_name=image_name,
            image_version=re.escape(image_version) if image_version else None,
            image_variant=image_variant,
            image_os=image_os,
            image_platform=[image_platform],
        ),
        dev_versions=dev_versions,
        clean_temporary=clean,
    )
    c = BakeryConfig.from_context(context, settings)
    results, err = c.dgoss_targets(platform=image_platform)

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
