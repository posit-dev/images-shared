from pathlib import Path
from typing import Annotated, List

import typer

from posit_bakery import error
from posit_bakery.cli.common import _wrap_project_load
from posit_bakery.log import stderr_console
from posit_bakery.util import auto_path


app = typer.Typer(no_args_is_help=True)


@app.command()
def dgoss(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_name: Annotated[str, typer.Option(help="The image name to isolate goss testing to.")] = None,
    image_version: Annotated[str, typer.Option(help="The image version to isolate goss testing to.")] = None,
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
        p.dgoss(image_name, image_version, run_option)
    except error.BakeryToolRuntimeError as e:
        stderr_console.print(f"[bright_red]❌ dgoss tests failed with exit code {e.exit_code}")
        raise typer.Exit(code=1)

    stderr_console.print(f"[green3]✅ Tests completed")
