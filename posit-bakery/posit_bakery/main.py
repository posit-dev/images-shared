import json
import os
import warnings
from pathlib import Path
from pprint import pformat
from typing import Annotated, List

import typer

from posit_bakery import bake_tools

app = typer.Typer()


def auto_path():
    context = Path(os.getcwd())
    return context


def auto_discover_bake_files_by_image_name(context, image_name):
    bake_file = []
    root_bake_file = context / "docker-bake.hcl"
    if root_bake_file.exists():
        bake_file.append(root_bake_file)
    else:
        typer.secho(
            f"WARNING: Unable to auto-discover a root bake file at {root_bake_file}, "
            f"this may cause unexpected behavior.",
            fg=typer.colors.YELLOW,
        )
    image_bake_file = context / image_name / "docker-bake.hcl"
    if not image_bake_file.exists():
        raise typer.secho(
            f"ERROR: Unable to auto-discover image bake file expected at {image_bake_file}. Exiting...",
            fg=typer.colors.RED,
        )
    bake_file.append(image_bake_file)
    override_bake_file = context / "docker-bake.override.hcl"
    if override_bake_file.exists():
        bake_file.append(override_bake_file)
    return bake_file


@app.command()
def plan(
        context: Path = None,
        image_name: str = None,
        targets: Annotated[List[str], typer.Option()] = None,
        bake_file: Annotated[List[Path], typer.Option()] = None,
):
    if context is None:
        context = auto_path()

    if image_name is None and bake_file is None:
        bake_file = list(context.rglob("docker-bake*.hcl"))
    elif image_name is not None and bake_file is None:
        bake_file = auto_discover_bake_files_by_image_name(context, image_name)
    elif bake_file is not None and image_name is not None:
        bake_file = list(bake_file)
        bake_file.extend(x for x in auto_discover_bake_files_by_image_name(context, image_name) if x not in bake_file)

    json_plan = bake_tools.get_bake_plan(context, targets, bake_file)
    typer.echo(json.dumps(json_plan, indent=2))


@app.command()
def test(
        context: Path = os.getcwd(),
        image_name: str = None,
        targets: Annotated[List[str], typer.Option()] = None,
        image_version: Annotated[str, typer.Option()] = None,
        bake_file: Annotated[List[Path], typer.Option()] = None,
        skip: Annotated[List[str], typer.Option()] = None,
):
    pass
