import typer

from posit_bakery.cli import ci, create, run, build, update, remove, clean, version
from posit_bakery.const import APP_NAME

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
    rich_help_panel="Image Building & Tools",
)(build.build)
app.command(name="bake", hidden=True)(build.build)
app.command(name="b", hidden=True)(build.build)

# Import the "run" subcommand
app.add_typer(
    run.app,
    name="run",
    help="Run extra tools/commands against images (aliases: r)",
    rich_help_panel="Image Building & Tools",
)
app.add_typer(run.app, name="r", hidden=True)

# Import the "create" subcommand
app.add_typer(
    create.app,
    name="create",
    help="Create new projects, images, and versions (aliases: c, new)",
    rich_help_panel="Project Management",
)
app.add_typer(create.app, name="c", hidden=True)
app.add_typer(create.app, name="new", hidden=True)

# Import the "update" subcommand
app.add_typer(
    update.app,
    name="update",
    help="Update managed files and configurations (aliases: u, up)",
    rich_help_panel="Project Management",
)
app.add_typer(update.app, name="up", hidden=True)
app.add_typer(update.app, name="u", hidden=True)

# Import the "remove" subcommand
app.add_typer(
    remove.app,
    name="remove",
    help="Remove images and versions from the project (aliases: rm, r)",
    rich_help_panel="Project Management",
)
app.add_typer(remove.app, name="rm", hidden=True)
app.add_typer(remove.app, name="r", hidden=True)

# Import the "ci" subcommand
app.add_typer(ci.app, name="ci", help="Construct a CI matrix from the project.", rich_help_panel="CI/CD & Maintenance")

# Import the "clean" subcommand
app.add_typer(
    clean.app, name="clean", help="Cleaning utilities for remote build caches", rich_help_panel="CI/CD & Maintenance"
)

# Import the "version" subcommand
app.command(name="version", help="Show the Posit Bakery version")(version.version)
