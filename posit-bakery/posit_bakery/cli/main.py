import typer

from posit_bakery.cli import create, common, run, build

app = typer.Typer(no_args_is_help=True, callback=common.__global_flags)

# Import the "create" subcommand
app.add_typer(create.app, name="create", help="Create new projects, images, and versions (aliases: c, new)")
app.add_typer(create.app, name="c", hidden=True)
app.add_typer(create.app, name="new", hidden=True)

# Import the "run" subcommand
app.add_typer(run.app, name="run", help="Run extra tools/commands against images (aliases: r)")
app.add_typer(run.app, name="r", hidden=True)

# Import the "build" subcommand
# Since "build" is a single command, we import the function directly rather than adding it as a typer subgroup
app.command(name="build", help="Build images using buildkit bake (aliases: b, bake)")(build.build)
app.command(name="bake", hidden=True)(build.build)
app.command(name="b", hidden=True)(build.build)
