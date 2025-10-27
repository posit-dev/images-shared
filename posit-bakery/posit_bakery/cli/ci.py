import json
import logging
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakerySettings, BakeryConfigFilter
from posit_bakery.const import DevVersionInclusionEnum
from posit_bakery.log import stdout_console
from posit_bakery.util import auto_path

app = typer.Typer(no_args_is_help=True)
log = logging.getLogger(__name__)


@app.command()
def matrix(
    image_name: Annotated[str | None, typer.Argument(help="The image name to list versions for.")] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(help="Include or exclude development versions defined in config."),
    ] = DevVersionInclusionEnum.EXCLUDE,
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
) -> None:
    """Generates a JSON matrix of image versions for CI workflows to consume

    The output is a JSON array of objects with the following structure:

    ```json
    [
      {
        "image": "image-name",
        "version": "version-name",
        "dev": false
      }
    ]
    ```
    """

    try:
        settings = BakerySettings(
            filter=BakeryConfigFilter(image_name=image_name),
            dev_versions=dev_versions,
        )
        c = BakeryConfig.from_context(context=context, settings=settings)
        images = [i for i in c.model.images]
        if image_name is not None:
            images = [i for i in images if i.name == image_name]

        data = []
        for img in images:
            for ver in img.versions:
                if ver.isDevelopmentVersion and dev_versions == DevVersionInclusionEnum.EXCLUDE:
                    continue
                if not ver.isDevelopmentVersion and dev_versions == DevVersionInclusionEnum.ONLY:
                    continue

                data.append(
                    {
                        "image": img.name,
                        "version": ver.name,
                        "dev": ver.isDevelopmentVersion,
                    }
                )

        stdout_console.print(json.dumps(data))

    except:
        log.exception("Failed to load bakery config")
        raise typer.Exit(code=1)
