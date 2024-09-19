from pathlib import Path
from typing import Annotated, List

import jinja2
import typer

from .templates import DOCKER_BAKE_TPL, CONTAINER_FILE_TPL

app = typer.Typer()


@app.command()
def new(root_path: Path, image_name: str, image_base: str = "posit/base:latest"):
    """Creates a skeleton for jumpstarting a new image.

    :param root_path: Path to create the new image directory in
    :param image_name: The new image's name
    :param image_base: The base for the new image
    :return:
    """
    if not root_path.exists():
        typer.echo(f"Root path '{root_path}' not found")
        raise typer.Exit(code=1)
    image_path = root_path / image_name
    if not image_path.exists():
        typer.echo(f"Creating new image directory {image_path}")
        image_path.mkdir()
    image_template_path = image_path / "template"
    if not image_template_path.exists():
        typer.echo(f"Creating new image templates directory {image_template_path}")
        image_template_path.mkdir()

    bake_file_path = image_path / "docker-bake.hcl"
    if not bake_file_path.exists():
        typer.echo(f"Creating new docker-bake file {bake_file_path}")
        tpl = jinja2.Environment().from_string(DOCKER_BAKE_TPL)
        rendered = tpl.render(image_name=image_name)
        with open(bake_file_path, "w") as f:
            f.write(rendered)

    containerfile_path = image_template_path / "Containerfile.jinja2"
    if not containerfile_path.exists():
        typer.echo(f"Creating new Containerfile template {containerfile_path}")
        tpl = jinja2.Environment().from_string(CONTAINER_FILE_TPL)
        rendered = tpl.render(base_image=image_base)
        with open(containerfile_path, "w") as f:
            f.write(rendered)


@app.command()
def render(
        image_path: Path,
        image_version: str,
        value: Annotated[List[str], typer.Option()] = None,
        skip_render_minimal: Annotated[bool, typer.Option()] = False,
):
    """Renders templates for an image to a versioned subdirectory of the image directory.

    This tool expects an image directory to use the following structure:
    .
    └── image_path/
        └── template/
            ├── optional_subdirectories/
            │   └── *.jinja2
            ├── *.jinja2
            └── Containerfile*.jinja2

    :param image_path: The path to the root of the image directory. This should be the path above the template directory.
    :param image_version: The new version to render the templates to.
    :param value: A key=value pair to pass to the templates. This can be repeated to pass multiple key=value pairs.
    :return:
    """

    # Check if the image path exists and exit if it doesn't
    if not image_path.exists():
        typer.echo(f"Image path '{image_path}' not found")
        raise typer.Exit(code=1)
    # Check for a template directory under the provided image path and exit if it doesn't exist
    image_template_path = image_path / "template"
    if not image_template_path.exists():
        typer.echo(f"Image templates path '{image_template_path}' not found")
        raise typer.Exit(code=1)
    # Create a new versioned directory for the image if it doesn't exist
    image_versioned_path = image_path / image_version
    if not image_versioned_path.exists():
        typer.echo(f"Creating new directory {image_versioned_path}")
        image_versioned_path.mkdir()

    # Parse the key=value pairs into a dictionary
    value_map = dict()
    if value is not None:
        for v in value:
            sp = v.split("=")
            if len(sp) != 2:
                typer.echo(f"Expected key=value pair, got '{v}'")
                raise typer.Exit(code=1)
            value_map[sp[0]] = sp[1]

    # Create a Jinja2 environment with the template directory as the loader
    e = jinja2.Environment(
        loader=jinja2.FileSystemLoader(image_template_path),
        autoescape=True,
        undefined=jinja2.StrictUndefined
    )
    for tpl_rel_path in e.list_templates():
        tpl = e.get_template(tpl_rel_path)

        # If the template is a Containerfile, render it to both a minimal and standard version
        if tpl_rel_path.startswith("Containerfile") and not skip_render_minimal:
            containerfile_base_name = tpl_rel_path.removesuffix(".jinja2")
            rendered = tpl.render(image_version=image_version, **value_map, is_minimal=False)
            with open(image_versioned_path / f"{containerfile_base_name}.std", "w") as f:
                f.write(rendered)
            rendered_min = tpl.render(image_version=image_version, **value_map, is_minimal=True)
            with open(image_versioned_path / f"{containerfile_base_name}.min", "w") as f:
                f.write(rendered_min)
            continue
        rendered = tpl.render(image_version=image_version, **value_map, is_minimal=False)
        rel_path = tpl_rel_path.removesuffix(".jinja2")
        target_dir = Path(image_versioned_path / rel_path).parent
        target_dir.mkdir(parents=True, exist_ok=True)
        with open(image_versioned_path / rel_path, "w") as f:
            f.write(rendered)
