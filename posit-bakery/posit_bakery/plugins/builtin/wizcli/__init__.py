import logging
import subprocess
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags, parse_dev_spec, exit_if_no_targets, normalize_platform
from posit_bakery.util import find_bin
from posit_bakery.config.config import BakeryConfig, BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.log import stderr_console
from posit_bakery.plugins.builtin.wizcli.command import WizCLIDriverEnum
from posit_bakery.plugins.builtin.wizcli.errors import WIZCLI_EXIT_CODE_POLICY_VIOLATION
from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions
from posit_bakery.plugins.builtin.wizcli.report import WizScanReportCollection
from posit_bakery.plugins.builtin.wizcli.suite import WizCLISuite
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult
from posit_bakery.settings import SETTINGS
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


class RichHelpPanelEnum(str, Enum):
    FILTERS = "Filters"
    WIZCLI = "WizCLI Options"
    AUTH = "Authentication"


class WizCLIPlugin(BakeryToolPlugin):
    name: str = "wizcli"
    description: str = "Scan container images for vulnerabilities with WizCLI"
    tool_options_class = WizCLIOptions

    def register_cli(self, app: typer.Typer) -> None:
        wizcli_app = typer.Typer(no_args_is_help=True)
        plugin = self

        @wizcli_app.command()
        @with_verbosity_flags
        def scan(
            context: Annotated[
                Path,
                typer.Option(
                    exists=True,
                    file_okay=False,
                    dir_okay=True,
                    readable=True,
                    writable=True,
                    resolve_path=True,
                    help="The root path to use. Defaults to the current working directory where invoked.",
                ),
            ] = auto_path(),
            image_name: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image name to isolate scanning to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_version: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image version to isolate scanning to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_variant: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image variant to isolate scanning to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_os: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image OS to isolate scanning to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_platform: Annotated[
                Optional[str],
                typer.Option(
                    show_default=SETTINGS.get_host_architecture(),
                    help="Which image build platform to scan, e.g. 'linux/amd64'. Filters the image targets and "
                    "selects which per-platform build digest is handed to wizcli.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            dev_versions: Annotated[
                Optional[DevVersionInclusionEnum],
                typer.Option(
                    help="Include or exclude development versions defined in config.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = DevVersionInclusionEnum.EXCLUDE,
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
            matrix_versions: Annotated[
                Optional[MatrixVersionInclusionEnum],
                typer.Option(
                    help="Include or exclude versions defined in image matrix.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = MatrixVersionInclusionEnum.EXCLUDE,
            latest: Annotated[
                Optional[bool],
                typer.Option(
                    "--latest",
                    help="Scan only the latest version of each image. Development versions are ignored by this filter.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = False,
            metadata_file: Annotated[
                Optional[Path],
                typer.Option(
                    help="Path to a build metadata file. If given, attempts to scan image artifacts in the file."
                ),
            ] = None,
            # WizCLI-specific options
            disabled_scanners: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Comma-separated scanners to disable (e.g. Vulnerability,Secret,Malware).",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            driver: Annotated[
                WizCLIDriverEnum,
                typer.Option(
                    help="Driver used to scan image.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = WizCLIDriverEnum.EXTRACT,
            policies: Annotated[
                Optional[str],
                typer.Option(
                    "--policies",
                    show_default=False,
                    help="Comma-separated Wiz policy IDs to apply to the scan. Overrides bakery.yaml if set.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            projects: Annotated[
                Optional[str],
                typer.Option(
                    "--projects",
                    show_default=False,
                    help="Comma-separated Wiz project IDs to scope the scan to. Overrides bakery.yaml if set.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            timeout: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Timeout for the scan (e.g. 1h, 30m).",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            no_publish: Annotated[
                Optional[bool],
                typer.Option(
                    "--no-publish",
                    help="Disable publishing scan results to the Wiz portal.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = False,
            log_file: Annotated[
                Optional[str],
                typer.Option(
                    "--log",
                    show_default=False,
                    help="File path for wizcli debug logs.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            # Auth options
            client_id: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Wiz service account client ID (overrides WIZ_CLIENT_ID env var).",
                    rich_help_panel=RichHelpPanelEnum.AUTH,
                ),
            ] = None,
            client_secret: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Wiz service account client secret (overrides WIZ_CLIENT_SECRET env var).",
                    rich_help_panel=RichHelpPanelEnum.AUTH,
                ),
            ] = None,
            use_device_code: Annotated[
                Optional[bool],
                typer.Option(
                    "--use-device-code",
                    help="Use device code flow for authentication.",
                    rich_help_panel=RichHelpPanelEnum.AUTH,
                ),
            ] = False,
            no_browser: Annotated[
                Optional[bool],
                typer.Option(
                    "--no-browser",
                    help="Do not open browser for device code flow.",
                    rich_help_panel=RichHelpPanelEnum.AUTH,
                ),
            ] = False,
        ) -> None:
            """Scan container images for vulnerabilities using WizCLI.

            \b
            Runs `wizcli scan container-image` against each image target in the project.
            Results are written as JSON files to the `results/wizcli/` directory.

            \b
            Images are expected to be available to the local Docker daemon. It is advised
            to run `build` before running wizcli scans.

            \b
            Requires wizcli to be installed on the system. The path to the binary can be
            set with the `WIZCLI_PATH` environment variable if not present in the system PATH.
            Authentication can be provided via `--client-id`/`--client-secret` options or
            the `WIZ_CLIENT_ID`/`WIZ_CLIENT_SECRET` environment variables.
            """
            platform = normalize_platform(image_platform)

            settings = BakerySettings(
                filter=BakeryConfigFilter(
                    image_name=image_name,
                    image_version=image_version,
                    image_variant=image_variant,
                    image_os=image_os,
                    image_platform=[platform],
                ),
                dev_versions=dev_versions,
                dev_spec=dev_spec,  # type: ignore[arg-type]  # typer requires str annotation; parse_dev_spec callback delivers DevBuildSpec at runtime
                matrix_versions=matrix_versions,
                latest=latest,
            )
            c = BakeryConfig.from_context(context, settings)

            exit_if_no_targets(c, settings)

            if metadata_file:
                c.load_build_metadata_from_file(metadata_file)

            results = plugin.execute(
                c.base_path,
                c.targets,
                platform=platform,
                disabled_scanners=disabled_scanners,
                driver=driver,
                policies=policies,
                projects=projects,
                client_id=client_id,
                client_secret=client_secret,
                use_device_code=use_device_code,
                no_browser=no_browser,
                timeout=timeout,
                no_publish=no_publish,
                log_file=log_file,
            )
            plugin.results(results)

        @wizcli_app.command()
        def tag(
            image_name: Annotated[
                str,
                typer.Option(
                    "--image-name",
                    help="Filter to a specific image name. Supports regular expressions.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = "",
            image_version: Annotated[
                str,
                typer.Option(
                    "--image-version",
                    help="Filter to a specific image version. A leading 'v' is stripped automatically.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = "",
            image_platform: Annotated[
                str,
                typer.Option(
                    "--image-platform",
                    help="Filter to a specific image platform (e.g. linux/amd64).",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = "",
            dev_versions: Annotated[
                DevVersionInclusionEnum,
                typer.Option(
                    "--dev-versions",
                    help="How to handle development versions.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = DevVersionInclusionEnum.EXCLUDE,
            dev_spec: Annotated[
                str | None,
                typer.Option(
                    "--dev-spec",
                    envvar="BAKERY_DEV_SPEC",
                    help="JSON spec for a dispatched dev build.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                    callback=parse_dev_spec,
                ),
            ] = None,
            matrix_versions: Annotated[
                Optional[MatrixVersionInclusionEnum],
                typer.Option(
                    "--matrix-versions",
                    help="How to handle matrix versions.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            context: Annotated[
                Path,
                typer.Option(
                    "--context",
                    help="The Bakery context to use (directory).",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = Path("."),
            metadata_files: Annotated[
                list[Path],
                typer.Argument(
                    help="Build metadata JSON files produced by the build step (one per platform).",
                    metavar="METADATA_FILE",
                ),
            ] = [],  # noqa: B006
            client_id: Annotated[
                Optional[str],
                typer.Option(
                    "--client-id",
                    envvar="WIZ_CLIENT_ID",
                    help="Wiz service account client ID.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
            client_secret: Annotated[
                Optional[str],
                typer.Option(
                    "--client-secret",
                    envvar="WIZ_CLIENT_SECRET",
                    help="Wiz service account client secret.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
        ):
            """Tag published container images in Wiz for code-to-cloud correlation.

            Reads per-platform digests from build metadata files and calls
            `wizcli tag {final-registry-repo}@{digest}` for each, using the same
            digest that was scanned. Wiz matches scan results to inventory by
            content digest, so this correctly links build findings to the
            published image regardless of which registry holds it.

            Per Wiz documentation, multi-platform images must be tagged per
            child digest — not by the multi-arch manifest list digest.

            Run after publishing (merge step), restricted to production builds.
            Authentication can be provided via `--client-id`/`--client-secret`
            or the `WIZ_CLIENT_ID`/`WIZ_CLIENT_SECRET` environment variables.
            """
            # Local import: only needed here, avoids a top-level dep on image_metadata.
            from posit_bakery.image.image_metadata import BuildMetadata

            platform = normalize_platform(image_platform) if image_platform else None
            settings = BakerySettings(
                filter=BakeryConfigFilter(
                    image_name=image_name,
                    image_version=image_version,
                    image_platform=[platform] if platform else [],
                ),
                dev_versions=dev_versions,
                dev_spec=dev_spec,  # type: ignore[arg-type]
                matrix_versions=matrix_versions,
            )
            c = BakeryConfig.from_path(context, settings=settings)
            exit_if_no_targets(c)

            # Build a map of image_name → set of final registry repo destinations.
            # Tag.destination gives "registry.host/namespace/image-name" without suffix.
            repo_map: dict[str, set[str]] = {}
            for target in c.targets:
                repos = {t.destination for t in target.tags if t.destination}
                repo_map.setdefault(target.image_name, set()).update(repos)

            wizcli_bin = find_bin(c.base_path, "wizcli", "WIZCLI_PATH") or "wizcli"
            errors: list[str] = []

            for mf in metadata_files:
                try:
                    metadata = BuildMetadata.model_validate_json(mf.read_text())
                except Exception as exc:
                    log.warning(f"Skipping {mf}: could not parse metadata ({exc})")
                    continue

                digest = metadata.container_image_digest
                if not digest:
                    log.warning(f"Skipping {mf}: no containerimage.digest")
                    continue

                # Derive image name from the metadata's primary tag path.
                # image.name is the temp registry ref; strip registry prefix to get
                # the image name, then look up the published repos from the config.
                meta_image_name = next(
                    (name for name in repo_map if any(name in tag for tag in metadata.image_tags)),
                    None,
                )
                if meta_image_name is None:
                    log.warning(f"Skipping {mf}: image name not matched in config")
                    continue

                for repo in sorted(repo_map[meta_image_name]):
                    ref = f"{repo}@{digest}"
                    cmd = [wizcli_bin, "tag", ref, "--no-color", "--no-style"]
                    if client_id:
                        cmd.extend(["--client-id", client_id])
                    if client_secret:
                        cmd.extend(["--client-secret", client_secret])
                    result = subprocess.run(cmd, capture_output=True, text=True)  # noqa: S603
                    if result.returncode != 0:
                        log.error(
                            f"wizcli tag failed for {ref}:\n"
                            f"  exit {result.returncode}: {result.stdout.strip() or result.stderr.strip()}"
                        )
                        errors.append(ref)
                    else:
                        log.info(f"Tagged {ref}")

            if errors:
                raise typer.Exit(code=1)

        app.add_typer(wizcli_app, name="wizcli", help="Scan container images for vulnerabilities with WizCLI")

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        platform: str | None = None,
        disabled_scanners: str | None = None,
        driver: WizCLIDriverEnum = WizCLIDriverEnum.EXTRACT,
        policies: str | None = None,
        projects: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        use_device_code: bool = False,
        no_browser: bool = False,
        timeout: str | None = None,
        no_publish: bool = False,
        log_file: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        suite = WizCLISuite(
            base_path,
            targets,
            platform=platform,
            disabled_scanners=disabled_scanners,
            driver=driver,
            policies=policies,
            projects=projects,
            client_id=client_id,
            client_secret=client_secret,
            use_device_code=use_device_code,
            no_browser=no_browser,
            timeout=timeout,
            no_publish=no_publish,
            log_file=log_file,
        )
        report_collection, errors = suite.run()

        error_list = []
        if errors is not None:
            if isinstance(errors, BakeryToolRuntimeErrorGroup):
                error_list = list(errors.exceptions)
            else:
                error_list = [errors]

        results = []
        for target in targets:
            report = None
            if target.image_name in report_collection:
                target_reports = report_collection[target.image_name]
                if target.uid in target_reports:
                    _, report = target_reports[target.uid]

            target_error = None
            for err in error_list:
                if hasattr(err, "message") and str(target) in err.message:
                    target_error = err
                    break

            exit_code = 0
            if target_error is not None:
                exit_code = getattr(target_error, "exit_code", 1)

            artifacts = {}
            if report is not None:
                artifacts["report"] = report
            if target_error is not None:
                artifacts["execution_error"] = target_error

            results.append(
                ToolCallResult(
                    exit_code=exit_code,
                    tool_name="wizcli",
                    target=target,
                    stdout="",
                    stderr="",
                    artifacts=artifacts if artifacts else None,
                )
            )

        return results

    def results(self, results: list[ToolCallResult]) -> None:
        report_collection = WizScanReportCollection()
        has_errors = False
        has_policy_violations = False
        errors = []

        for result in results:
            if result.artifacts and "report" in result.artifacts:
                report_collection.add_report(result.target, result.artifacts["report"])
            if result.artifacts and "execution_error" in result.artifacts:
                err = result.artifacts["execution_error"]
                if getattr(err, "exit_code", 1) == WIZCLI_EXIT_CODE_POLICY_VIOLATION:
                    has_policy_violations = True
                else:
                    has_errors = True
                errors.append(err)

        if report_collection:
            stderr_console.print(report_collection.table())

        if has_policy_violations:
            stderr_console.print("-" * 80)
            stderr_console.print(
                "Security policy violation(s) detected. These issues must be addressed.",
                style="bright_red bold",
            )
            for err in errors:
                if getattr(err, "exit_code", 1) == WIZCLI_EXIT_CODE_POLICY_VIOLATION:
                    stderr_console.print(f"  {err.message}", style="error")

        if has_errors:
            stderr_console.print("-" * 80)
            for err in errors:
                if getattr(err, "exit_code", 1) != WIZCLI_EXIT_CODE_POLICY_VIOLATION:
                    stderr_console.print(err, style="error")
            stderr_console.print("\u274c wizcli scan(s) failed to execute", style="error")

        if has_errors or has_policy_violations:
            raise typer.Exit(code=1)

        stderr_console.print("\u2705 Scans completed", style="success")
