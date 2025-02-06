import typer

from posit_bakery.cli import create, common, run

app = typer.Typer(no_args_is_help=True, callback=common.__global_flags)

# Import the "create" subcommand
app.add_typer(create.app, name="create", help="Create new projects, images, and versions (aliases: c, new)")
app.add_typer(create.app, name="c", hidden=True)
app.add_typer(create.app, name="new", hidden=True)
app.add_typer(run.app, name="run", help="Run commands against images (aliases: r)")
app.add_typer(run.app, name="r", hidden=True)
