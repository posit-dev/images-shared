from enum import Enum

import typer

from posit_bakery.cli import ci, create, run, build, update, remove, clean, version
from posit_bakery.settings import APP_NAME


class RichHelpPanelEnum(str, Enum):
    """Enum for categorizing options into rich help panels."""

    IMAGE_BUILDING_AND_TOOLS = "Image Building & Tools"
    PROJECT_MANAGEMENT = "Project Management"
    CI_CD_AND_MAINTENANCE = "CI/CD & Maintenance"


app = typer.Typer(
    name=APP_NAME,
    no_args_is_help=True,
    rich_markup_mode="markdown",
    help="A tool for building, testing, and managing container images",
)

# Import the "build" subcommand
# Since "build" is a single command, we import the function directly rather than adding it as a typer subgroup
app.command(
    name="build",
    help="Build images using buildkit bake (aliases: b, bake)",
    rich_help_panel=RichHelpPanelEnum.IMAGE_BUILDING_AND_TOOLS,
)(build.build)
app.command(name="bake", hidden=True)(build.build)
app.command(name="b", hidden=True)(build.build)

# Import the "run" subcommand
app.add_typer(
    run.app,
    name="run",
    help="Run extra tools/commands against images (aliases: r)",
    rich_help_panel=RichHelpPanelEnum.IMAGE_BUILDING_AND_TOOLS,
)
app.add_typer(run.app, name="r", hidden=True)

# Import the "create" subcommand
app.add_typer(
    create.app,
    name="create",
    help="Create new projects, images, and versions (aliases: c, new)",
    rich_help_panel=RichHelpPanelEnum.PROJECT_MANAGEMENT,
)
app.add_typer(create.app, name="c", hidden=True)
app.add_typer(create.app, name="new", hidden=True)

# Import the "update" subcommand
app.add_typer(
    update.app,
    name="update",
    help="Update managed files and configurations (aliases: u, up)",
    rich_help_panel=RichHelpPanelEnum.PROJECT_MANAGEMENT,
)
app.add_typer(update.app, name="up", hidden=True)
app.add_typer(update.app, name="u", hidden=True)

# Import the "remove" subcommand
app.add_typer(
    remove.app,
    name="remove",
    help="Remove images and versions from the project (aliases: rm, r)",
    rich_help_panel=RichHelpPanelEnum.PROJECT_MANAGEMENT,
)
app.add_typer(remove.app, name="rm", hidden=True)
app.add_typer(remove.app, name="r", hidden=True)

# Import the "ci" subcommand
app.add_typer(
    ci.app,
    name="ci",
    help="Construct a CI matrix from the project.",
    rich_help_panel=RichHelpPanelEnum.CI_CD_AND_MAINTENANCE,
)

# Import the "clean" subcommand
app.add_typer(
    clean.app,
    name="clean",
    help="Cleaning utilities for remote build caches",
    rich_help_panel=RichHelpPanelEnum.CI_CD_AND_MAINTENANCE,
)

# Import the "version" subcommand
app.command(name="version", help="Show the Posit Bakery version")(version.version)

# Import the "version" subcommand
app.command(name="version", help="Show the Posit Bakery version")(version.version)
