import logging
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags, exit_if_no_targets, parse_dev_spec
from posit_bakery.config.config import BakeryConfig, BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.log import stderr_console
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
                    help="Filters which image build platform to scan.",
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
            # Trivy-specific options
            severity: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Comma-separated severities to report (e.g. HIGH,CRITICAL).",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
            fail_on_severity: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Comma-separated severities that fail the scan if found (e.g. CRITICAL). "
                    "Unset means findings never fail the scan.",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
            disabled_scanners: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Comma-separated scanners to disable (e.g. secret,license,misconfig).",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
            timeout: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Timeout for the scan (e.g. 1h, 10m).",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
            trivy_config: Annotated[
                Optional[Path],
                typer.Option(
                    show_default=False,
                    help="Path to a native trivy.yaml config file. Defaults to '<image>/trivy.yaml' if present.",
                    rich_help_panel=RichHelpPanelEnum.TRIVY,
                ),
            ] = None,
        ) -> None:
            """Scan container images for vulnerabilities using Trivy.

            \b
            Runs `trivy image` against each image target in the project.
            Results are written as SARIF files to the `results/trivy/` directory.

            \b
            Images are expected to be available to the local Docker daemon, or
            resolvable to a registry digest via --metadata-file. It is advised
            to run `build` before running trivy scans.

            \b
            Requires trivy to be installed on the system. The path to the binary can be
            set with the `TRIVY_PATH` environment variable if not present in the system PATH.
            """
            platform = image_platform or SETTINGS.architecture
            if not platform.startswith("linux/"):
                platform = f"linux/{platform}"

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
                scan_platform=platform,
                severity=severity,
                fail_on_severity=fail_on_severity,
                disabled_scanners=disabled_scanners,
                timeout=timeout,
                trivy_config=trivy_config,
            )
            plugin.results(results)

        app.add_typer(trivy_app, name="trivy", help="Scan container images for vulnerabilities with Trivy")

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        scan_platform: str | None = None,
        severity: str | None = None,
        fail_on_severity: str | None = None,
        disabled_scanners: str | None = None,
        timeout: str | None = None,
        trivy_config: Path | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        suite = TrivySuite(
            base_path,
            targets,
            scan_platform=scan_platform,
            severity=severity,
            disabled_scanners=disabled_scanners,
            timeout=timeout,
            trivy_config=trivy_config,
        )
        report_collection, errors = suite.run()

        # Each TrivyCommand already resolved its own per-target TrivyOptions
        # (variant overrides image, per get_tool_option); reuse that resolution
        # here so --fail-on-severity falls back to bakery.yaml the same way
        # --severity/--disabled-scanners/--timeout already do in TrivyCommand.
        tool_options_by_uid = {cmd.image_target.uid: cmd.tool_options for cmd in suite.trivy_commands}

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

            target_tool_options = tool_options_by_uid.get(target.uid)
            resolved_fail_on_severity = fail_on_severity or (
                ",".join(target_tool_options.failOnSeverity)
                if target_tool_options and target_tool_options.failOnSeverity
                else None
            )
            breach_severities = (
                [s.strip().upper() for s in resolved_fail_on_severity.split(",") if s.strip()]
                if resolved_fail_on_severity
                else None
            )

            severity_breach = bool(report and breach_severities and report.breaches(breach_severities))

            exit_code = 0
            if target_error is not None:
                exit_code = getattr(target_error, "exit_code", 1)
            elif severity_breach:
                exit_code = 1

            artifacts = {}
            if report is not None:
                artifacts["report"] = report
            if target_error is not None:
                artifacts["execution_error"] = target_error
            if severity_breach:
                artifacts["severity_breach"] = True

            results.append(
                ToolCallResult(
                    exit_code=exit_code,
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
                errors.append(result.artifacts["execution_error"])
                has_errors = True
            if result.artifacts and result.artifacts.get("severity_breach"):
                has_severity_breach = True

        if report_collection:
            stderr_console.print(report_collection.table())

        if has_severity_breach:
            stderr_console.print("-" * 80)
            stderr_console.print(
                "Findings matching one or more of the configured --fail-on-severity severities were detected.",
                style="bright_red bold",
            )

        if has_errors:
            stderr_console.print("-" * 80)
            for err in errors:
                stderr_console.print(err, style="error")
            stderr_console.print("❌ trivy scan(s) failed to execute", style="error")

        if has_errors or has_severity_breach:
            raise typer.Exit(code=1)

        stderr_console.print("✅ Scans completed", style="success")
