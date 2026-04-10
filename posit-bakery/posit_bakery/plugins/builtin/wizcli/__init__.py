import logging
import re
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.cli.common import with_verbosity_flags
from posit_bakery.config.config import BakeryConfig, BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.error import BakeryToolRuntimeErrorGroup
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.log import stderr_console
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
            matrix_versions: Annotated[
                Optional[MatrixVersionInclusionEnum],
                typer.Option(
                    help="Include or exclude versions defined in image matrix.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = MatrixVersionInclusionEnum.EXCLUDE,
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
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Driver used to scan image (extract, mount, mountWithLayers).",
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
                bool,
                typer.Option(
                    help="Disable publishing scan results to the Wiz portal.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = False,
            scan_context_id: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Context identifier that defines scan granularity.",
                    rich_help_panel=RichHelpPanelEnum.WIZCLI,
                ),
            ] = None,
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
                bool,
                typer.Option(
                    help="Use device code flow for authentication.",
                    rich_help_panel=RichHelpPanelEnum.AUTH,
                ),
            ] = False,
            no_browser: Annotated[
                bool,
                typer.Option(
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
            platform = image_platform or SETTINGS.architecture
            platform = f"linux/{platform}"

            settings = BakerySettings(
                filter=BakeryConfigFilter(
                    image_name=image_name,
                    image_version=re.escape(image_version) if image_version else None,
                    image_variant=image_variant,
                    image_os=image_os,
                    image_platform=[platform],
                ),
                dev_versions=dev_versions,
                matrix_versions=matrix_versions,
            )
            c = BakeryConfig.from_context(context, settings)

            if metadata_file:
                c.load_build_metadata_from_file(metadata_file)

            results = plugin.execute(
                c.base_path,
                c.targets,
                disabled_scanners=disabled_scanners,
                driver=driver,
                client_id=client_id,
                client_secret=client_secret,
                use_device_code=use_device_code,
                no_browser=no_browser,
                timeout=timeout,
                no_publish=no_publish,
                scan_context_id=scan_context_id,
                log_file=log_file,
            )
            plugin.results(results)

        app.add_typer(wizcli_app, name="wizcli", help="Scan container images for vulnerabilities with WizCLI")

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        disabled_scanners: str | None = None,
        driver: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        use_device_code: bool = False,
        no_browser: bool = False,
        timeout: str | None = None,
        no_publish: bool = False,
        scan_context_id: str | None = None,
        log_file: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        suite = WizCLISuite(
            base_path,
            targets,
            disabled_scanners=disabled_scanners,
            driver=driver,
            client_id=client_id,
            client_secret=client_secret,
            use_device_code=use_device_code,
            no_browser=no_browser,
            timeout=timeout,
            no_publish=no_publish,
            scan_context_id=scan_context_id,
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
