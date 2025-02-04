import typer

from posit_bakery.cli import create

app = typer.Typer(no_args_is_help=True)

# Import the "create" subcommand
app.add_typer(create.app, name="create", help="Create new projects, images, and versions (aliases: c, new)")
app.add_typer(create.app, name="c", hidden=True)
app.add_typer(create.app, name="new", hidden=True)
