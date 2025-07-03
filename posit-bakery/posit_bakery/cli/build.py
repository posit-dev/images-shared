import logging
from pathlib import Path
from typing import Annotated, Optional

import pydantic
from python_on_whales.exceptions import DockerException
import typer

from posit_bakery import error
from posit_bakery.cli.common import _wrap_project_load
from posit_bakery.log import stderr_console, stdout_console
from posit_bakery.models import Project
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


def print_plan(project: Project, image_name: str, image_version: str, image_type: str) -> None:
    log.info(f"Rendering bake plan...")
    try:
        plan = project.render_bake_plan(image_name, image_version, image_type)
    except error.BakeryError as e:
        stderr_console.print(e)
        stderr_console.print(f"❌ Failed to render bake plan", style="error")
        raise typer.Exit(code=1)
    except pydantic.ValidationError as e:
        stderr_console.print(e)
        stderr_console.print(f"❌ Failed to render bake plan", style="error")
        stderr_console.print(
            "Please correct the above data validation error(s) and try again.", style="info"
        )
        raise typer.Exit(code=1)

    stdout_console.print_json(plan.model_dump_json(), indent=2)
    raise typer.Exit()


def build(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_name: Annotated[Optional[str], typer.Option(help="The image name to isolate plan rendering to.")] = None,
    image_version: Annotated[
        Optional[str], typer.Option(help="The image version to isolate plan rendering to.")
    ] = None,
    image_type: Annotated[Optional[str], typer.Option(help="The image type to isolate plan rendering to.")] = None,
    plan: Annotated[
        Optional[bool], typer.Option("--plan", help="Print the bake plan and exit.")
    ] = False,
    load: Annotated[Optional[bool], typer.Option(help="Load the image to Docker after building.")] = False,
    push: Annotated[Optional[bool], typer.Option(help="Push the image to the registry after building.")] = False,
    no_cache: Annotated[Optional[bool], typer.Option(help="Disable caching for build.")] = False,
    builder: Annotated[Optional[str], typer.Option(help="The buildkit builder to use.")] = None,
    stream_logs: Annotated[Optional[bool], typer.Option(help="Enable streaming container logs.")] = False,
) -> None:
    """Builds images in the context path using buildx bake

    If no options are provided, the command will auto-discover all images in the current
    directory and generate a temporary bake plan to execute for all targets.

    Requires the Docker Engine and CLI to be installed and running.
    """
    # TODO; Add skip_override back in
    p: Project = _wrap_project_load(context)

    if plan:
        print_plan(p, image_name, image_version, image_type)

    try:
        p.build(
            load,
            push,
            image_name,
            image_version,
            image_type,
            cache=not no_cache,
            builder=builder,
            stream_logs=stream_logs,
        )
    except DockerException as e:
        stderr_console.print(f"❌ Build failed with exit code {e.return_code}", style="error")
        raise typer.Exit(code=1)

    stderr_console.print("✅Build completed", style="success")
