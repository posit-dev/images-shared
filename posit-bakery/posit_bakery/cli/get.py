import logging
from typing import Annotated

import typer

from posit_bakery import settings
from posit_bakery.log import stderr_console
from posit_bakery.models.manifest import find_os
from posit_bakery.templating.filters import condense
from posit_bakery.web.version.product import get_product_artifact_by_stream
from posit_bakery.web.version.product.const import ProductEnum, ReleaseStreamEnum

log = logging.getLogger(__name__)

app = typer.Typer(no_args_is_help=True)


@app.command()
def version(
    product: Annotated[ProductEnum, typer.Argument(help="The product to get the latest version for.")],
    release_stream: Annotated[
        ReleaseStreamEnum, typer.Argument(help="The release stream to get the latest version for.")
    ],
    os_name: Annotated[
        str, typer.Argument(help="The operating system to get the version for in the form of {name}-{version}.")
    ] = "ubuntu-22.04",
):
    _os = find_os(condense(os_name))
    try:
        result = get_product_artifact_by_stream(product, release_stream, _os)
        stderr_console.print_json(result.model_dump_json())
    except Exception as e:
        log.error(f"An error occurred while retrieving the version.")
        if settings.DEBUG:
            stderr_console.print_exception(max_frames=5, show_locals=True)
