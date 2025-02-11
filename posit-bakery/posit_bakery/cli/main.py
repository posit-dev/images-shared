import typer

from posit_bakery.cli import create, common, run, build

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

# Import the "run" subcommand
app.add_typer(run.app, name="run", help="Run extra tools/commands against images (aliases: r)")
app.add_typer(run.app, name="r", hidden=True)

# Import the "build" subcommand
# Since "build" is a single command, we import the function directly rather than adding it as a typer subgroup
app.add_typer(build.app, name="build", help="Build images using buildkit bake (aliases: b, bake)")
app.add_typer(build.app, name="bake", hidden=True)
app.add_typer(build.app, name="b", hidden=True)
