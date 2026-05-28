import glob
import json
import logging
import python_on_whales
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags, parse_dev_spec
from posit_bakery.config import BakeryConfig
from posit_bakery.config.config import BakerySettings, BakeryConfigFilter, version_matches
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.log import stderr_console, stdout_console
from posit_bakery.registry_management.dockerhub.readme import push_readmes
from posit_bakery.util import auto_path

app = typer.Typer(no_args_is_help=True)
log = logging.getLogger(__name__)


class RichHelpPanelEnum(str, Enum):
    """Enum for categorizing options into rich help panels."""

    FILTERS = "Filters"


class BakeryCIMatrixFieldEnum(str, Enum):
    VERSION = "version"
    DEV = "dev"
    PLATFORM = "platform"


@app.command()
@with_verbosity_flags
def matrix(
    image_name: Annotated[str | None, typer.Argument(help="The image name to isolate matrix to.")] = None,
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(
            help="Include or exclude development versions defined in config.", rich_help_panel=RichHelpPanelEnum.FILTERS
        ),
    ] = DevVersionInclusionEnum.EXCLUDE,
    dev_channel: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-channel",
            help="Filter development versions to a specific release channel.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    dev_stream: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-stream",
            help="Deprecated: use --dev-channel instead.",
            hidden=True,
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    matrix_versions: Annotated[
        Optional[MatrixVersionInclusionEnum],
        typer.Option(
            help="Include or exclude versions defined in image matrix.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = MatrixVersionInclusionEnum.EXCLUDE,
    image_version: Annotated[
        Optional[str],
        typer.Option(
            show_default=False,
            help="The image version to filter to.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    exclude: Annotated[
        Optional[list[BakeryCIMatrixFieldEnum]],
        typer.Option(help="Fields to exclude splitting the matrix by."),
    ] = None,
    context: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
            help="The root path to use. Defaults to the current working directory where invoked.",
        ),
    ] = auto_path(),
    dev_spec: Annotated[
        str | None,
        typer.Option(
            "--dev-spec",
            envvar="BAKERY_DEV_SPEC",
            help='JSON spec for a dispatched dev build. Ex: \'{"version": "2026.05.0-dev+185-gSHA", "channel": "daily"}\'',
            rich_help_panel=RichHelpPanelEnum.FILTERS,
            callback=parse_dev_spec,
        ),
    ] = None,
) -> None:
    """Generates a JSON matrix of image versions for CI workflows to consume

    The output is a JSON array of objects with the following structure:

    \b
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

    if dev_stream is not None:
        log.warning("--dev-stream is deprecated, use --dev-channel instead.")
        if dev_channel is None:
            dev_channel = dev_stream
    try:
        settings = BakerySettings(
            filter=BakeryConfigFilter(image_name=image_name),
            dev_versions=dev_versions,
            dev_channel=dev_channel,
            dev_spec=dev_spec,  # type: ignore[arg-type]  # typer requires str annotation; parse_dev_spec callback delivers DevBuildSpec at runtime
        )
        c = BakeryConfig.from_context(context=context, settings=settings)
        images = [i for i in c.model.images]
        if image_name is not None:
            images = [i for i in images if i.name == image_name]

        data = []
        for img in images:
            entry = {"image": img.name}
            versions = img.versions
            if (img.matrix is None and matrix_versions == MatrixVersionInclusionEnum.ONLY) or (
                img.matrix is not None and matrix_versions == MatrixVersionInclusionEnum.EXCLUDE
            ):
                continue
            elif img.matrix is not None and matrix_versions != MatrixVersionInclusionEnum.EXCLUDE:
                versions = img.matrix.to_image_versions()
            for ver in versions:
                included, _ = ver.matches_dev_filter(dev_versions, dev_channel)
                if not included:
                    continue
                if image_version is not None and not version_matches(ver.name, image_version):
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

        if image_version is not None and not data:
            log.error(f"No matrix entries matched --image-version '{image_version}'")
            raise typer.Exit(code=1)

        stdout_console.print(json.dumps(data))

    except typer.Exit:
        raise
    except:
        log.exception("Failed to load bakery config")
        raise typer.Exit(code=1)


@app.command()
@with_verbosity_flags
def merge(
    metadata_file: Annotated[list[Path], typer.Argument(help="Path to input build metadata JSON file(s) to merge.")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory where invoked.")
    ] = auto_path(),
    temp_registry: Annotated[
        Optional[str],
        typer.Option(
            help="Temporary registry to use for multiplatform split/merge builds.",
            rich_help_panel="Build Configuration & Outputs",
        ),
    ] = None,
    dry_run: Annotated[
        bool, typer.Option(help="If set, the merged images will not be pushed to the registry.")
    ] = False,
    dev_channel: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-channel",
            help="Filter development versions to a specific release channel.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    dev_stream: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-stream",
            help="Deprecated: use --dev-channel instead.",
            hidden=True,
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
):
    """Alias for `bakery ci publish --no-enable-soci`.

    Preserved for back-compat. New callers should prefer `bakery ci publish`.
    """
    publish(
        metadata_file=metadata_file,
        context=context,
        temp_registry=temp_registry,
        enable_soci=False,
        dry_run=dry_run,
        dev_channel=dev_channel,
    )


@app.command()
@with_verbosity_flags
def publish(
    metadata_file: Annotated[list[Path], typer.Argument(help="Path to input build metadata JSON file(s).")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory.")
    ] = auto_path(),
    temp_registry: Annotated[
        Optional[str],
        typer.Option(
            help="Temporary registry to use for split/merge builds.", rich_help_panel="Build Configuration & Outputs"
        ),
    ] = None,
    enable_soci: Annotated[
        bool,
        typer.Option("--enable-soci/--no-enable-soci", help="Run SOCI conversion between merge-create and merge-copy."),
    ] = False,
    dry_run: Annotated[bool, typer.Option(help="If set, no images will be pushed.")] = False,
    dev_channel: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-channel",
            help="Filter development versions to a specific release channel.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    dev_stream: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-stream",
            help="Deprecated: use --dev-channel instead.",
            hidden=True,
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
) -> None:
    """Publish multi-platform images by composing oras index-create →
    optional soci-convert → oras index-copy.

    Temporary indexes are left in place and cleaned up out-of-band by the
    clean.yml workflow (bakery clean temp-registry) rather than deleted here.

    Replaces `bakery ci merge`; the latter is preserved as a thin alias
    that calls this command with `--no-enable-soci`.
    """
    # Imports kept local to mirror existing patterns and to avoid bloating
    # module load time when this command isn't invoked.
    from posit_bakery.plugins.builtin.oras.oras import (
        OrasIndexCopyWorkflow,
        OrasIndexCreateWorkflow,
        find_oras_bin,
    )
    from posit_bakery.plugins.registry import get_plugin

    if dev_stream is not None:
        log.warning("--dev-stream is deprecated, use --dev-channel instead.")
        if dev_channel is None:
            dev_channel = dev_stream
    settings = BakerySettings(
        dev_versions=DevVersionInclusionEnum.INCLUDE,
        dev_channel=dev_channel,
        matrix_versions=MatrixVersionInclusionEnum.INCLUDE,
        clean_temporary=False,
        temp_registry=temp_registry,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, settings)

    resolved_files: list[Path] = []
    for f in metadata_file:
        s = str(f)
        if "*" in s or "?" in s or "[" in s:
            resolved_files.extend(sorted(Path(x).absolute() for x in glob.glob(s)))
        else:
            resolved_files.append(f.absolute())
    metadata_file = resolved_files

    log.info(f"Reading targets from {', '.join(f.name for f in metadata_file)}")

    files_ok = True
    loaded_targets: list[str] = []
    for f in metadata_file:
        try:
            loaded_targets.extend(config.load_build_metadata_from_file(f))
        except Exception as e:
            log.error(f"Failed to load metadata from file '{f}': {e}")
            files_ok = False
    if not files_ok:
        raise typer.Exit(code=1)

    loaded_targets = list(set(loaded_targets))  # Deduplicate targets in case of overlap across files
    log.info(f"Found {len(loaded_targets)} targets")
    log.debug(", ".join(loaded_targets))

    oras_bin = find_oras_bin(config.base_path)
    targets = sorted(config.targets, key=lambda t: t.push_sort_key)

    # Phase 1: index create. Failures abort.
    temp_refs: dict[str, str] = {}
    for t in targets:
        if not t.get_merge_sources():
            log.debug(f"Skipping target '{t}' (no merge sources).")
            continue
        if not t.settings.temp_registry:
            log.error(f"Cannot publish '{t}': temp_registry not configured.")
            raise typer.Exit(code=1)
        res = OrasIndexCreateWorkflow(
            oras_bin=oras_bin,
            image_target=t,
            annotations=t.labels,
        ).run(dry_run=dry_run)
        if not res.success:
            log.error(f"index-create failed for '{t}': {res.error}")
            raise typer.Exit(code=1)
        temp_refs[t.uid] = res.temp_ref  # type: ignore[assignment]

    # Phase 2: SOCI convert (conditional).
    if enable_soci:
        soci = get_plugin("soci")
        soci_results = soci.execute(
            config.base_path,
            targets,
            source_refs=temp_refs,
            dry_run=dry_run,
        )
        for r in soci_results:
            artifacts = r.artifacts or {}
            if artifacts.get("skipped"):
                continue
            wf = artifacts.get("workflow_result")
            if r.exit_code != 0:
                soci.results(soci_results)  # raises typer.Exit(1)
            if wf and getattr(wf, "destination_ref", None):
                temp_refs[r.target.uid] = wf.destination_ref

    # Phase 3: index copy.
    copy_failed = False
    for t in targets:
        if t.uid not in temp_refs:
            continue
        copy = OrasIndexCopyWorkflow(
            oras_bin=oras_bin,
            image_target=t,
        ).run(source=temp_refs[t.uid], dry_run=dry_run)
        if not copy.success:
            log.error(f"index-copy failed for '{t}': {copy.error}")
            copy_failed = True

    # The temporary indexes (and any SOCI-converted variants) are intentionally
    # left in place; they are cleaned up out-of-band by the clean.yml workflow
    # (bakery clean temp-registry) rather than deleted here.

    if copy_failed:
        raise typer.Exit(code=1)


@app.command()
@with_verbosity_flags
def readme(
    context: Annotated[
        Path,
        typer.Option(
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            resolve_path=True,
            help="The root path to use. Defaults to the current working directory where invoked.",
        ),
    ] = auto_path(),
    dev_versions: Annotated[
        Optional[DevVersionInclusionEnum],
        typer.Option(
            help="Include or exclude development versions defined in config.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = DevVersionInclusionEnum.INCLUDE,
    dev_channel: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-channel",
            help="Filter development versions to a specific release channel.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    dev_stream: Annotated[
        Optional[ReleaseChannelEnum],
        typer.Option(
            "--dev-stream",
            help="Deprecated: use --dev-channel instead.",
            hidden=True,
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    matrix_versions: Annotated[
        Optional[MatrixVersionInclusionEnum],
        typer.Option(
            help="Include or exclude versions defined in image matrix.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = MatrixVersionInclusionEnum.INCLUDE,
) -> None:
    """Push image READMEs to Docker Hub.

    Pushes the README.md from each image directory to the corresponding Docker Hub
    repository description. Only pushes for eligible images: latest versions,
    matrix versions, and non-development versions with Docker Hub registries configured.

    Requires DOCKER_HUB_README_USERNAME and DOCKER_HUB_README_PASSWORD environment
    variables to be set with a Personal Access Token (PAT). Organization Access Tokens
    cannot update repository descriptions.
    """
    if dev_stream is not None:
        log.warning("--dev-stream is deprecated, use --dev-channel instead.")
        if dev_channel is None:
            dev_channel = dev_stream
    settings = BakerySettings(
        dev_versions=dev_versions,
        dev_channel=dev_channel,
        matrix_versions=matrix_versions,
    )
    config: BakeryConfig = BakeryConfig.from_context(context, settings)

    try:
        count = push_readmes(config.targets)
    except (ValueError, RuntimeError) as e:
        stderr_console.print(f"❌ {e}", style="error")
        raise typer.Exit(code=1)

    if count > 0:
        stderr_console.print(f"✅ Pushed {count} README(s) to Docker Hub", style="success")
    else:
        stderr_console.print("No READMEs pushed", style="dim")
