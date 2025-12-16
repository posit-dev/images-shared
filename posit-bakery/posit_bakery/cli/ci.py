import json
import logging
from enum import Enum
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


class BakeryCIMatrixFieldEnum(str, Enum):
    VERSION = "version"
    DEV = "dev"
    PLATFORM = "platform"


@app.command()
def matrix(
    image_name: Annotated[str | None, typer.Argument(help="The image name to list versions for.")] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(help="Include or exclude development versions defined in config."),
    ] = DevVersionInclusionEnum.EXCLUDE,
    exclude: Annotated[
        Optional[list[BakeryCIMatrixFieldEnum]],
        typer.Option(help="Fields to exclude splitting the matrix by."),
    ] = None,
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
        "dev": false,
        "platform": "linux/amd64"
      }
    ]
    ```
    """
    if exclude is None:
        exclude = []

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
            entry = {"image": img.name}
            for ver in img.versions:
                if ver.isDevelopmentVersion and dev_versions == DevVersionInclusionEnum.EXCLUDE:
                    continue
                if not ver.isDevelopmentVersion and dev_versions == DevVersionInclusionEnum.ONLY:
                    continue

                if BakeryCIMatrixFieldEnum.VERSION not in exclude:
                    entry["version"] = ver.name
                if BakeryCIMatrixFieldEnum.DEV not in exclude:
                    entry["dev"] = ver.isDevelopmentVersion
                if BakeryCIMatrixFieldEnum.PLATFORM not in exclude:
                    for platform in ver.supported_platforms:
                        entry["platform"] = platform
                        data.append(entry.copy())
                else:
                    data.append(entry.copy())

        stdout_console.print(json.dumps(data))

    except:
        log.exception("Failed to load bakery config")
        raise typer.Exit(code=1)
