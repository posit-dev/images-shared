import json
import logging
import re
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags, parse_dev_spec
from posit_bakery.config import BakeryConfig
from posit_bakery.config.changeset import classify_changes, ImageChangeSet, MatrixSelection
from posit_bakery.config.config import BakerySettings, BakeryConfigFilter, version_matches
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from posit_bakery.config.image.version import ImageVersion
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.log import stderr_console, stdout_console
from posit_bakery.registry_management.dockerhub.readme import find_oversized_readmes, push_readmes
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


def _resolve_changed_files(base_ref: str | None, changed_files_from: str | None, rebase_root: Path) -> list[str] | None:
    """Return the changed-file list for change-aware filtering, or None to disable it.

    ``--changed-files-from`` takes precedence over ``--base-ref``, and the two use
    different path conventions.

    - ``--base-ref`` runs ``git diff`` (paths relative to the repo root), then
      rebases them onto ``rebase_root`` (the bakery context) and drops paths outside
      it. If the diff against ``base_ref`` fails for any reason (unreachable ref,
      all-zero SHA, unrelated histories), logs a warning and returns ``None``
      (disabling filtering) rather than raising.
    - ``--changed-files-from`` paths are used verbatim and must already be relative
      to the bakery context root. They are not rebased, so do not pipe raw
      ``git diff --name-only`` output here unless the context is the repo root. Use
      ``--base-ref`` when you have a git checkout.
    """
    if changed_files_from is not None:
        if base_ref is not None:
            log.warning("--base-ref is ignored because --changed-files-from is set.")
        if changed_files_from == "-":
            raw = sys.stdin.read()
        else:
            raw = Path(changed_files_from).read_text()
        return [line.strip() for line in raw.splitlines() if line.strip()]

    if base_ref is None:
        return None

    # Local import: git diff is only needed on this rarely-used code path.
    from posit_bakery.config.changeset import git_changed_files

    # Not wrapped in the fail-safe below: failing here means rebase_root itself
    # isn't a git checkout at all, a more fundamental misconfiguration than a
    # base_ref that doesn't diff cleanly, and should surface loudly rather than
    # silently fall back to a full build.
    repo_root = _git_repo_root(rebase_root)

    try:
        changed = git_changed_files(repo_root, base_ref)
    except subprocess.CalledProcessError as e:
        # base_ref may not diff cleanly (e.g. github.event.before is the all-zero SHA
        # on a branch's first push, or an unreachable ref after a force-push). Fail
        # safe to a full build rather than crashing the CI run.
        log.warning(
            "Could not diff against base-ref %r (%s); falling back to a full build.",
            base_ref,
            e.stderr.strip() if e.stderr else e,
        )
        return None

    rebased: list[str] = []
    for rel in changed:
        abs_path = repo_root / rel
        try:
            rebased.append((abs_path.relative_to(rebase_root)).as_posix())
        except ValueError:
            # Changed file lives outside this bakery context (monorepo) -> not our concern.
            continue
    return rebased


def _git_repo_root(rebase_root: Path) -> Path:
    """Return the git repository root containing ``rebase_root``.

    Failing here means ``rebase_root`` isn't a git checkout at all — a more
    fundamental misconfiguration than anything downstream should silently
    paper over, so this is not wrapped in a fail-safe.
    """
    toplevel = subprocess.run(
        ["git", "-C", str(rebase_root), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return Path(toplevel)


def _resolve_base_bakery_yaml(
    base_ref: str | None, changed_files: list[str] | None, config_file: Path
) -> str | None:
    """Return bakery.yaml's text content at ``base_ref``, or None to skip semantic diffing.

    Returns None (no git call made) when there's no base_ref, no changed-files
    list, or bakery.yaml isn't actually one of the changed files. Otherwise
    attempts to read it at base_ref; any failure (unreachable ref, path didn't
    exist at that ref, etc.) logs a warning and returns None rather than
    raising — the caller treats None as "compare unavailable, fail safe to a
    full build," the same shape as _resolve_changed_files' own fail-safe.
    """
    if base_ref is None or changed_files is None or config_file.name not in changed_files:
        return None

    # Local import: git I/O is only needed on this rarely-used code path.
    from posit_bakery.config.changeset import git_show_file

    repo_root = _git_repo_root(config_file.parent)
    rel_path = config_file.relative_to(repo_root).as_posix()

    try:
        return git_show_file(repo_root, base_ref, rel_path)
    except subprocess.CalledProcessError as e:
        log.warning(
            "Could not read bakery.yaml at base-ref %r (%s); disabling semantic bakery.yaml diffing for this run.",
            base_ref,
            e.stderr.strip() if e.stderr else e,
        )
        return None


def _version_selected(ver: ImageVersion, cs: ImageChangeSet) -> bool:
    """Whether a candidate version was touched by the change set.

    Pure narrowing predicate. Type/channel eligibility (--dev-versions,
    --matrix-versions, --dev-channel) is enforced separately by the caller via
    matches_dev_filter, so this only answers "did the PR touch this version?".
    """
    if ver.isDevelopmentVersion:
        return cs.include_dev
    if ver.isMatrixVersion:
        return cs.include_matrix_latest and ver.latest
    # Plain release version.
    return cs.include_all_release or ver.name in cs.versions


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
    base_ref: Annotated[
        Optional[str],
        typer.Option(
            "--base-ref",
            envvar="BAKERY_BASE_REF",
            show_default=False,
            help="Git ref to diff against (merge-base) to build only changed images/versions. "
            "When unset, the full matrix is emitted.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    changed_files_from: Annotated[
        Optional[str],
        typer.Option(
            "--changed-files-from",
            show_default=False,
            help="Read changed file paths (one per line, '-' for stdin), relative to the "
            "bakery context root, instead of running git diff. Overrides --base-ref.",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
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
        images = [i for i in c.model.images if image_name is None or re.search(image_name, i.name) is not None]

        selection: MatrixSelection | None = None
        changed = _resolve_changed_files(base_ref, changed_files_from, c.base_path)
        if changed is not None:
            selection = classify_changes(c, changed)
            if selection.full:
                # Fail-safe / repo-wide change: behave exactly as a full matrix.
                selection = None
            else:
                log.info(
                    "Change-aware matrix: %s",
                    {name: vars(cs) for name, cs in selection.images.items()} or "no affected images",
                )

        # A --dev-spec carrying a channel implies the matrix should be filtered to that
        # channel. The shared CI workflow folds the dispatched channel into the dev-spec
        # and stops passing --dev-channel, so without this the other channels' dev versions
        # would still be emitted (only the matching one gets its version pinned).
        effective_dev_channel = settings.dev_channel
        if effective_dev_channel is None and settings.dev_spec is not None:
            effective_dev_channel = settings.dev_spec.channel

        data = []
        for img in images:
            if selection is not None and img.name not in selection.images:
                continue
            cs = selection.images[img.name] if selection is not None else None

            entry = {"image": img.name}

            # Candidate versions honor --dev-versions / --matrix-versions identically
            # whether or not change-aware filtering is active. Preserves the matrix+dev
            # filtering fix (commit 92c72833 / generate_image_targets): when matrix
            # versions are included, fold the already-loaded dev versions into the
            # matrix product per the dev_versions setting so they survive the
            # matches_dev_filter check below.
            versions = list(img.versions)
            if img.matrix is None and matrix_versions == MatrixVersionInclusionEnum.ONLY:
                continue
            elif img.matrix is not None:
                if matrix_versions != MatrixVersionInclusionEnum.EXCLUDE:
                    if dev_versions == DevVersionInclusionEnum.ONLY:
                        pass  # img.versions has dev versions; matrix prod versions all fail the dev filter
                    elif dev_versions == DevVersionInclusionEnum.INCLUDE:
                        dev_versions_loaded = [v for v in img.versions if v.isDevelopmentVersion]
                        versions = img.matrix.to_image_versions() + dev_versions_loaded
                    else:
                        versions = img.matrix.to_image_versions()

            for ver in versions:
                # The caller's flags decide which kinds of version are eligible
                # (release / dev / matrix), in both full and change-aware modes.
                included, _ = ver.matches_dev_filter(dev_versions, effective_dev_channel)
                if not included:
                    continue
                # In change-aware mode the change set then narrows to the versions
                # the PR actually touched. It only ever removes candidates.
                if cs is not None and not _version_selected(ver, cs):
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
    image_name: Annotated[
        Optional[str],
        typer.Option(
            help="Filter merge to a specific image name (regex, e.g. '^workbench$').",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
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
):
    """Alias for `bakery ci publish`.

    Preserved for back-compat. New callers should prefer `bakery ci publish`.
    SOCI conversion is driven by per-image/variant `soci` options.
    """
    if dev_stream is not None:
        log.warning("--dev-stream is deprecated, use --dev-channel instead.")
        if dev_channel is None:
            dev_channel = dev_stream
    publish(
        metadata_file=metadata_file,
        context=context,
        image_name=image_name,
        temp_registry=temp_registry,
        dry_run=dry_run,
        dev_channel=dev_channel,
        dev_spec=dev_spec,  # type: ignore[arg-type]  # typer requires str annotation; parse_dev_spec callback delivers DevBuildSpec at runtime
    )


@app.command()
@with_verbosity_flags
def publish(
    metadata_file: Annotated[list[Path], typer.Argument(help="Path to input build metadata JSON file(s).")],
    context: Annotated[
        Path, typer.Option(help="The root path to use. Defaults to the current working directory.")
    ] = auto_path(),
    image_name: Annotated[
        Optional[str],
        typer.Option(
            help="Filter publish to a specific image name (regex, e.g. '^workbench$').",
            rich_help_panel=RichHelpPanelEnum.FILTERS,
        ),
    ] = None,
    temp_registry: Annotated[
        Optional[str],
        typer.Option(
            help="Temporary registry to use for split/merge builds.", rich_help_panel="Build Configuration & Outputs"
        ),
    ] = None,
    jobs: Annotated[
        Optional[int],
        typer.Option(
            "--jobs",
            "-j",
            min=1,
            show_default=False,
            help="Maximum number of targets to publish concurrently. "
            "Defaults to the BAKERY_MAX_CONCURRENCY env var or a built-in default.",
        ),
    ] = None,
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
    """Publish multi-platform images by composing oras index-create →
    soci-convert → oras index-copy.

    Which targets are converted is driven by configuration: each target is
    converted only when its resolved SOCI options have ``enabled: true``
    (set via the ``soci`` tool options on an image or variant). Targets
    without SOCI enabled pass through the convert phase untouched. Conversion
    runs in standalone (no containerd) mode via oras.

    Temporary indexes are left in place and cleaned up out-of-band by the
    clean.yml workflow (bakery clean temp-registry) rather than deleted here.

    The orchestration itself lives in the ``imagetools`` plugin
    (:meth:`ImageToolsPlugin.publish`); this command is a thin wrapper.

    Replaces `bakery ci merge`; the latter is preserved as a thin alias.
    """
    # Imported locally to avoid bloating module load time when this command
    # isn't invoked.
    from posit_bakery.plugins.registry import get_plugin

    if dev_stream is not None:
        log.warning("--dev-stream is deprecated, use --dev-channel instead.")
        if dev_channel is None:
            dev_channel = dev_stream
    get_plugin("imagetools").publish(
        metadata_file=metadata_file,
        context=context,
        image_name=image_name,
        temp_registry=temp_registry,
        dry_run=dry_run,
        dev_channel=dev_channel,
        dev_spec=dev_spec,
        jobs=jobs,
    )


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
    check: Annotated[
        bool,
        typer.Option(
            "--check",
            help="Validate README length against Docker Hub's limit, without authenticating or pushing.",
        ),
    ] = False,
) -> None:
    """Push image READMEs to Docker Hub.

    Pushes the README.md from each image directory to the corresponding Docker Hub
    repository description. Only pushes for eligible images: latest versions,
    matrix versions, and non-development versions with Docker Hub registries configured.

    Requires DOCKER_HUB_README_USERNAME and DOCKER_HUB_README_PASSWORD environment
    variables to be set with a Personal Access Token (PAT). Organization Access Tokens
    cannot update repository descriptions.

    With --check, only validates that eligible READMEs are within Docker Hub's
    25,000-byte full_description limit. Requires no credentials and makes no network
    calls, so it is safe to run in fork PR CI.
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

    if check:
        violations = find_oversized_readmes(config.targets)
        if violations:
            for violation in violations:
                stderr_console.print(f"❌ {violation}", style="error")
            raise typer.Exit(code=1)
        stderr_console.print("✅ All READMEs are within Docker Hub's length limit", style="success")
        return

    try:
        count = push_readmes(config.targets)
    except (ValueError, RuntimeError) as e:
        stderr_console.print(f"❌ {e}", style="error")
        raise typer.Exit(code=1)

    if count > 0:
        stderr_console.print(f"✅ Pushed {count} README(s) to Docker Hub", style="success")
    else:
        stderr_console.print("No READMEs pushed", style="dim")
