import typer

from posit_bakery import __version__
from posit_bakery.log import stdout_console


def version():
    """Display the version of Posit Bakery"""
    stdout_console.print(f"Posit Bakery v{__version__}", highlight=False)
    raise typer.Exit()
