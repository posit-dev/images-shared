import logging
from pathlib import Path
from typing import Annotated, Optional, List

import pydantic
import typer

from posit_bakery import error
from posit_bakery.log import stdout_console, stderr_console, init_logging
from posit_bakery.models import Project
from posit_bakery.util import auto_path

DEFAULT_BASE_IMAGE: str = "docker.io/library/ubuntu:22.04"


log: logging.Logger  # Global log variable, set in the callback function

app = typer.Typer()


@app.callback()
def __callback_logging(
    verbose: Annotated[Optional[bool], typer.Option("--verbose", "-v", help="Enable debug logging")] = False,
    quiet: Annotated[Optional[bool], typer.Option("--quiet", "-q", help="Supress all output except errors")] = False,
) -> None:
    """Callback to configure logging based on the debug and quiet flags."""
    global log

    if verbose and quiet:
        raise typer.BadParameter("Cannot set both --verbose and --quiet flags.")

    log_level: str | int = logging.INFO
    if verbose:
        log_level = logging.DEBUG
    elif quiet:
        log_level = logging.ERROR

    init_logging(log_level)

    log = logging.getLogger(__name__)


def _wrap_project_load(context: Path) -> Project:
    try:
        project = Project.load(context)
    except error.BakeryContextDirectoryNotFoundError:
        stderr_console.print_exception(max_frames=0, show_locals=False)
        stderr_console.print(f"[bright_red]❌ Failed to load project from '{context}'")
        stderr_console.print("Please ensure you are in the correct working directory or specify a path with --context.")
        raise typer.Exit(code=1)
    except error.BakeryConfigNotFoundError:
        stderr_console.print_exception(max_frames=0, show_locals=False)
        stderr_console.print(f"[bright_red]❌ Failed to load project from '{context}'")
        stderr_console.print("Please ensure you have a valid project in the specified directory.")
        raise typer.Exit(code=1)
    except error.BakeryImageError:
        stderr_console.print_exception(max_frames=0, show_locals=False)
        stderr_console.print(f"[bright_red]❌ Failed to load project from '{context}'")
        stderr_console.print("Please correct the above error and try again.")
        raise typer.Exit(code=1)
    except (error.BakeryModelValidationError, error.BakeryModelValidationErrorGroup) as e:
        stderr_console.print(e)
        stderr_console.print(f"[bright_red]❌ Failed to load project from '{context}'")
        stderr_console.print("Please correct the above data validation error(s) and try again.")
        raise typer.Exit(code=1)
    except error.BakeryError:
        stderr_console.print_exception(max_frames=5)
        stderr_console.print(f"[bright_red]❌ Failed to load project from '{context}'")
        raise typer.Exit(code=1)
    except Exception:
        stderr_console.print_exception(max_frames=20)
        stderr_console.print(f"[bright_red]❌ Failed to load project from '{context}'")
        raise typer.Exit(code=1)
    return project


@app.command()
def new(
    image_name: Annotated[str, typer.Argument(help="The image name to create a skeleton for.")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_base: Annotated[str, typer.Option(help="The base to use for the new image.")] = DEFAULT_BASE_IMAGE,
) -> None:
    """Creates a quickstart skeleton for a new image in the context path

    This tool will create a new directory in the context path with the following structure:
    .
    └── image_name/
        ├── manifest.toml
        └── template/
            ├── deps/
            │   └── packages.txt.jinja2
            ├── test/
            │   └── goss.yaml.jinja2
            └── Containerfile.jinja2
    """
    p = _wrap_project_load(context)
    # TODO: This will fail on projects with no config.toml, we should build in a full "new project" expectation in that case
    try:
        p.create_image(image_name, image_base)
    except error.BakeryError:
        stderr_console.print_exception(max_frames=5, show_locals=False)
        stderr_console.print(f"[bright_red]❌ Failed to create image '{image_name}'")
        raise typer.Exit(code=1)
    except Exception:
        stderr_console.print_exception(max_frames=20)
        stderr_console.print(f"[bright_red]❌ Failed to create image '{image_name}'")
        raise typer.Exit(code=1)

    stderr_console.print(f"[green3]✅ Successfully created image '{image_name}'")


@app.command()
def render(
    image_name: Annotated[
        str, typer.Argument(help="The image directory to render. This should be the path above the template directory.")
    ],
    image_version: Annotated[str, typer.Argument(help="The new version to render the templates to.")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    value: Annotated[
        List[str], typer.Option(help="A 'key=value' pair to pass to the templates. Accepts multiple pairs.")
    ] = None,
    mark_latest: Annotated[bool, typer.Option(help="Skip marking the latest version of the image.")] = True,
    force: Annotated[bool, typer.Option(help="Force overwrite of existing version directory.")] = False,
) -> None:
    """Renders templates for an image to a versioned subdirectory of the image directory.

    This tool expects an image directory to use the following structure as generated by `bakery new`:
    .
    └── image_path/
        └── template/
            ├── optional_subdirectories/
            │   └── *.jinja2
            ├── *.jinja2
            └── Containerfile*.jinja2
    """
    p = _wrap_project_load(context)

    # TODO: Determine whether we still want to support the value map via the CLI or in a file
    # Parse the key=value pairs into a dictionary
    value_map = dict()
    if value is not None:
        for v in value:
            sp = v.split("=")
            if len(sp) != 2:
                stderr_console.print(f"[bright_red]❌ Expected key=value pair, got [bold]'{v}'")
                raise typer.Exit(code=1)
            value_map[sp[0]] = sp[1]

    try:
        p.create_image_version(
            image_name=image_name,
            image_version=image_version,
            template_values=value_map,
            mark_latest=mark_latest,
            force=force,
        )
    except error.BakeryConfigError:
        stderr_console.print_exception(max_frames=5, show_locals=False)
        stderr_console.print(f"[bright_red]❌ Failed to create version '{image_name}/{image_version}'")
        raise typer.Exit(code=1)

    stderr_console.print(f"[green3]✅ Successfully created version '{image_name}/{image_version}'")


@app.command()
def plan(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_name: Annotated[str, typer.Option(help="The image name to isolate plan rendering to.")] = None,
    image_version: Annotated[
        str, typer.Option(help="The image version to isolate plan rendering to. Must be used with --image-name.")
    ] = None,
    skip_override: Annotated[
        bool, typer.Option(help="Skip loading config.override.toml file for auto-discovery.")
    ] = False,
    output_file: Annotated[
        Path, typer.Option(help="The file to write the rendered plan to. Defaults to bake-plan.json.")
    ] = Path(auto_path(), "bake-plan.json"),
) -> None:
    """Generates a plan in JSON based off of provided or auto-discovered bake files.

    If no options are provided, the command will auto-discover all bake files in the current
    directory and generate a plan for all targets.

    If only an image name is provided, the command will auto-discover that image's bake file and will also load the
    root bake file and any override bake files if they exist.
    """
    # TODO; Add skip_override back in
    p = _wrap_project_load(context)

    try:
        bake_plan = p.render_bake_plan(image_name, image_version)
    except error.BakeryError as e:
        log.error(e)
        stderr_console.print(f"[bright_red]❌ Failed to render bake plan")
        raise typer.Exit(code=1)
    except pydantic.ValidationError as e:
        log.error(e)
        stderr_console.print(f"[bright_red]❌ Failed to render bake plan")
        stderr_console.print("Please correct the above data validation error(s) and try again.")
        raise typer.Exit(code=1)

    stdout_console.print_json(bake_plan.model_dump_json(), indent=2)
    with open(output_file, "w") as f:
        f.write(bake_plan.model_dump_json(indent=2))


@app.command()
def build(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_name: Annotated[str, typer.Option(help="The image name to isolate plan rendering to.")] = None,
    image_version: Annotated[str, typer.Option(help="The image version to isolate plan rendering to.")] = None,
    image_type: Annotated[str, typer.Option(help="The image type to isolate plan rendering to.")] = None,
    skip_override: Annotated[
        bool, typer.Option(help="Skip loading docker-bake.override.hcl files for auto-discovery.")
    ] = False,
    load: Annotated[bool, typer.Option(help="Load the image to Docker after building.")] = False,
    push: Annotated[bool, typer.Option(help="Push the image to the registry after building.")] = False,
    option: Annotated[
        List[str], typer.Option(help="Additional build options to pass to docker buildx. Multiple can be provided.")
    ] = None,
) -> None:
    """Builds images in the context path using buildx bake

    If no options are provided, the command will auto-discover all images in the current
    directory and generate a temporary bake plan to execute for all targets.

    Requires the Docker Engine and CLI to be installed and running.
    """
    # TODO; Add skip_override back in
    p = _wrap_project_load(context)

    try:
        p.build(load, push, image_name, image_version, image_type, option)
    except error.BakeryToolRuntimeError as e:
        stderr_console.print(f"[bright_red]❌ Build failed with exit code {e.exit_code}")
        raise typer.Exit(code=1)

    stderr_console.print(f"[green3]✅ Build completed")


@app.command()
def dgoss(
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    image_name: Annotated[str, typer.Option(help="The image name to isolate goss testing to.")] = None,
    image_version: Annotated[str, typer.Option(help="The image version to isolate goss testing to.")] = None,
    skip_override: Annotated[
        bool, typer.Option(help="Skip loading config.override.toml file for auto-discovery.")
    ] = False,
    option: Annotated[
        List[str], typer.Option(help="Additional runtime options to pass to dgoss. Multiple can be provided.")
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
        p.dgoss(image_name, image_version, option)
    except error.BakeryToolRuntimeError as e:
        stderr_console.print(f"[bright_red]❌ dgoss tests failed with exit code {e.exit_code}")
        raise typer.Exit(code=1)

    stderr_console.print(f"[green3]✅ Tests completed")
