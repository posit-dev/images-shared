import logging
from typing import Annotated

import typer

from posit_bakery.web.versions import ProductEnum, ReleaseStreamEnum

log = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True)


@app.command()
def version(
    product: Annotated[ProductEnum, typer.Argument(help="The product to get the latest version for.")],
    release_stream: Annotated[
        ReleaseStreamEnum, typer.Argument(help="The release stream to get the latest version for.")
    ],
):
    pass
