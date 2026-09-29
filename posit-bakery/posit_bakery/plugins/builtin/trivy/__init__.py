import logging
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags, parse_dev_spec, exit_if_no_targets, normalize_platform
from posit_bakery.config.config import BakeryConfig, BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.log import stderr_console
from posit_bakery.plugins.builtin.trivy.errors import TRIVY_EXIT_CODE_SEVERITY_THRESHOLD
from posit_bakery.plugins.builtin.trivy.options import TrivyOptions
from posit_bakery.plugins.builtin.trivy.report import TrivyReportCollection
from posit_bakery.plugins.builtin.trivy.suite import TrivySuite
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult
from posit_bakery.settings import SETTINGS
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


class RichHelpPanelEnum(str, Enum):
    FILTERS = "Filters"
    TRIVY = "Trivy Options"


class TrivyPlugin(BakeryToolPlugin):
    name: str = "trivy"
    description: str = "Scan container images for vulnerabilities with Trivy"
    tool_options_class = TrivyOptions

    def register_cli(self, app: typer.Typer) -> None:
        trivy_app = typer.Typer(no_args_is_help=True)
        plugin = self

        @trivy_app.command()
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
                    "selects which per-platform build digest is handed to trivy.",
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
            # Trivy-specific options. Each is CLI-passthrough: when explicitly set, it wins
            # over any bakery.yaml-configured TrivyOptions for the same field
            # (TrivyCommand.command's per-field precedence), mirroring the WizCLI plugin's
            # policies/projects split. Defaults are None (not False/""), so an unset flag
            # never masks a bakery.yaml value -- only an explicit flag does.
            severity: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Comma-separated severities to scan for (e.g. CRITICAL,HIGH). Overrides bakery.yaml if set.",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
            ignore_unfixed: Annotated[
                Optional[bool],
                typer.Option(
                    "--ignore-unfixed/--no-ignore-unfixed",
                    help="Ignore vulnerabilities without an available fix. Overrides bakery.yaml if set.",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
            skip_files: Annotated[
                Optional[str],
                typer.Option(
                    "--skip-files",
                    show_default=False,
                    help="Comma-separated file paths to skip during scanning. Overrides bakery.yaml if set.",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
            skip_dirs: Annotated[
                Optional[str],
                typer.Option(
                    "--skip-dirs",
                    show_default=False,
                    help="Comma-separated directory paths to skip during scanning. Overrides bakery.yaml if set.",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
            exit_code: Annotated[
                Optional[int],
                typer.Option(
                    "--exit-code",
                    show_default=False,
                    help="Exit code trivy returns when vulnerabilities are found. Overrides bakery.yaml if set.",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
        ) -> None:
            """Scan container images for vulnerabilities using Trivy.

            \b
            Runs `trivy image` against each image target in the project.
            Results are written as SARIF files to the `results/trivy/` directory.

            \b
            Images are expected to be available to the local Docker daemon. It is advised
            to run `build` before running trivy scans.

            \b
            Requires trivy to be installed on the system. The path to the binary can be
            set with the `TRIVY_PATH` environment variable if not present in the system PATH.
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
                severity=severity.split(",") if severity else None,
                ignore_unfixed=ignore_unfixed,
                skip_files=skip_files.split(",") if skip_files else None,
                skip_dirs=skip_dirs.split(",") if skip_dirs else None,
                exit_code=exit_code,
            )
            plugin.results(results)

        app.add_typer(trivy_app, name="trivy", help="Scan container images for vulnerabilities with Trivy")

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        platform: str | None = None,
        severity: list[str] | None = None,
        ignore_unfixed: bool | None = None,
        skip_files: list[str] | None = None,
        skip_dirs: list[str] | None = None,
        exit_code: int | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        suite = TrivySuite(
            base_path,
            targets,
            platform=platform,
            severity=severity,
            ignore_unfixed=ignore_unfixed,
            skip_files=skip_files,
            skip_dirs=skip_dirs,
            exit_code=exit_code,
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

            result_exit_code = 0
            if target_error is not None:
                result_exit_code = getattr(target_error, "exit_code", 1)

            artifacts = {}
            if report is not None:
                artifacts["report"] = report
            if target_error is not None:
                artifacts["execution_error"] = target_error

            results.append(
                ToolCallResult(
                    exit_code=result_exit_code,
                    tool_name="trivy",
                    target=target,
                    stdout="",
                    stderr="",
                    artifacts=artifacts if artifacts else None,
                )
            )

        return results

    def results(self, results: list[ToolCallResult]) -> None:
        report_collection = TrivyReportCollection()
        has_errors = False
        has_severity_breach = False
        errors = []

        for result in results:
            if result.artifacts and "report" in result.artifacts:
                report_collection.add_report(result.target, result.artifacts["report"])
            if result.artifacts and "execution_error" in result.artifacts:
                err = result.artifacts["execution_error"]
                if getattr(err, "exit_code", 1) == TRIVY_EXIT_CODE_SEVERITY_THRESHOLD:
                    has_severity_breach = True
                else:
                    has_errors = True
                errors.append(err)

        if report_collection:
            stderr_console.print(report_collection.table())

        if has_severity_breach:
            stderr_console.print("-" * 80)
            stderr_console.print(
                "Severity threshold breach(es) detected. These issues must be addressed.",
                style="bright_red bold",
            )
            for err in errors:
                if getattr(err, "exit_code", 1) == TRIVY_EXIT_CODE_SEVERITY_THRESHOLD:
                    stderr_console.print(f"  {err.message}", style="error")

        if has_errors:
            stderr_console.print("-" * 80)
            for err in errors:
                if getattr(err, "exit_code", 1) != TRIVY_EXIT_CODE_SEVERITY_THRESHOLD:
                    stderr_console.print(err, style="error")
            stderr_console.print("\u274c trivy scan(s) failed to execute", style="error")

        if has_severity_breach or has_errors:
            raise typer.Exit(code=1)

        stderr_console.print("\u2705 Scans completed", style="success")
