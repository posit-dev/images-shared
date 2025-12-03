import glob
import json
import logging
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer
from python_on_whales import DockerException

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
        typer.Option(help="Include or exclude development versions defined in config."),
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


@app.command()
def merge(
    metadata_file: Annotated[list[Path], typer.Argument(help="Path to input build metadata JSON file(s) to merge.")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    dry_run: Annotated[
        bool, typer.Option(help="If set, the merged images will not be pushed to the registry.")
    ] = False,
):
    """Merges multiple metadata files with single-platform images into a single multi-platform image by UID.

    This command is intended for use in CI workflows that utilize native builders for multiplatform builds.
    Easier multiplatform builds can be achieved by using emulation (Docker and QEMU), but builds in emulation typically
    suffer severe performance disadvantages.

    This command should be ran after multiple `bakery build --strategy build --platform <platform>
    --metadata-file <path> --temp-registry <registry>` commands have been executed for different platforms. The
    resulting metadata files can be fed into this command to merge and push combined multi-platform images. Matches are
    made by the top-level Image UID keys in the metadata files. Single entries with no other matches will be tagged and
    pushed as is. If an entry has no matching UID in the project, it will be skipped with a delayed error.

    Metadata files are expected to be JSON with the following structure:

    ```json
    {
      "<Image UID>": {metadata...}
    }
    ```
    """
    settings = BakerySettings(
        dev_versions=DevVersionInclusionEnum.INCLUDE,
        clean_temporary=False,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, settings)

    # Resolve glob patterns in metadata_file arguments
    resolved_files: list[Path] = []
    for file in metadata_file:
        if "*" in str(file) or "?" in str(file) or "[" in str(file):
            resolved_files.extend(sorted(Path(x) for x in glob.glob(str(file))))
        else:
            resolved_files.append(file)
    metadata_file = resolved_files
    log.info(f"Reading targets from {', '.join(str(f) for f in metadata_file)}")

    image_digests: dict[str, list[str]] = {}
    for file in metadata_file:
        if not file.is_file():
            log.error(f"Metadata file '{file}' does not exist")
            raise typer.Exit(code=1)
        with open(file, "r") as f:
            data = json.load(f)
        for uid, metadata in data.items():
            image_name = metadata.get("image.name")
            if not image_name:
                log.error(f"Metadata file '{file}' is missing 'image.name' for image UID '{uid}'")
                raise typer.Exit(code=1)
            digest = metadata.get("containerimage.digest")
            if not digest:
                log.error(f"Metadata file '{file}' is missing 'containerimage.digest' for image UID '{uid}'")
                raise typer.Exit(code=1)
            image_digests.setdefault(uid, []).append(f"{image_name}@{digest}")

    log.info(f"Found {len(image_digests.keys())} targets")
    log.debug(json.dumps(image_digests, indent=2, sort_keys=True))

    for uid, sources in image_digests.items():
        target = config.get_image_target_by_uid(uid)
        log.info(f"Merging {len(sources)} sources for image UID '{uid}'")
        try:
            manifest = target.merge(sources=sources, dry_run=dry_run)
            if dry_run:
                stdout_console.print_json(manifest.model_dump_json(indent=2, exclude_unset=True, exclude_none=True))
        except DockerException as e:
            log.error(f"Error merging sources for UID '{uid}'")
            log.error(str(e))
