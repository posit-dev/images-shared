import typer

from posit_bakery.cli import ci, create, common, run, build, update, remove, clean
from posit_bakery.log import stderr_console

app = typer.Typer(
    name="bakery",
    no_args_is_help=True,
    callback=common.__global_flags,
    help="A tool for building, testing, and managing container images",
)

# Import the "create" subcommand
app.add_typer(create.app, name="create", help="Create new projects, images, and versions (aliases: c, new)")
app.add_typer(create.app, name="c", hidden=True)
app.add_typer(create.app, name="new", hidden=True)

# Import the "update" subcommand
app.add_typer(update.app, name="update", help="Update managed files and configurations (aliases: u, up)")
app.add_typer(update.app, name="up", hidden=True)
app.add_typer(update.app, name="u", hidden=True)

# Import the "remove" subcommand
app.add_typer(remove.app, name="remove", help="Remove images and versions from the project (aliases: rm, r)")
app.add_typer(remove.app, name="rm", hidden=True)
app.add_typer(remove.app, name="r", hidden=True)

# Import the "ci" subcommand
app.add_typer(ci.app, name="ci", help="Construct a CI matrix from the project.")

# Import the "run" subcommand
app.add_typer(run.app, name="run", help="Run extra tools/commands against images (aliases: r)")
app.add_typer(run.app, name="r", hidden=True)

# Import the "build" subcommand
# Since "build" is a single command, we import the function directly rather than adding it as a typer subgroup
app.command(name="build", help="Build images using buildkit bake (aliases: b, bake)")(build.build)
app.command(name="bake", hidden=True)(build.build)
app.command(name="b", hidden=True)(build.build)

# Import the "clean" subcommand
app.add_typer(clean.app, name="clean", help="Cleaning utilities for remote build caches")


@app.command(name="help")
@run.app.command(name="help")
@create.app.command(name="help")
def _help(ctx: typer.Context) -> None:
    """Show this message and exit."""
    stderr_console.print(ctx.parent.get_help())
