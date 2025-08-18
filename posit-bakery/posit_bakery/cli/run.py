import logging
from pathlib import Path
from typing import Annotated, List, Optional

import typer

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
    privileged: Annotated[
        Optional[bool], typer.Option("--privileged", help="Alias for \"--run-opt='--privileged'\"")
    ] = False,
    run_option: Annotated[
        List[str],
        typer.Option(
            "--run-opt",
            help="Additional runtime options to pass to dgoss. Multiple can be provided.",
        ),
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

    if run_option is None:
        run_option = []
    if privileged and "--privileged" not in run_option:
        run_option.append("--privileged")

    results, err = p.dgoss(image_name, image_version, image_type, run_option)
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
