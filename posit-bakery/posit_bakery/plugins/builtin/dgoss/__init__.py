import logging
import re
import warnings
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
from posit_bakery.plugins.builtin.dgoss.options import GossOptions
from posit_bakery.plugins.builtin.dgoss.report import GossJsonReportCollection
from posit_bakery.plugins.builtin.dgoss.suite import DGossSuite
from posit_bakery.plugins.protocol import ToolCallResult
from posit_bakery.settings import SETTINGS
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


class RichHelpPanelEnum(str, Enum):
    """Enum for categorizing options into rich help panels."""

    FILTERS = "Filters"


class DGossPlugin:
    name: str = "dgoss"
    description: str = "Run Goss tests against container images"
    tool_options_class = GossOptions

    def register_cli(self, app: typer.Typer) -> None:
        """Register the dgoss CLI commands with the given Typer app."""
        dgoss_app = typer.Typer(no_args_is_help=True)

        # Capture self for use in closure
        plugin = self

        @dgoss_app.command()
        @with_verbosity_flags
        def run(
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
                    help="The image name to isolate goss testing to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_version: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image version to isolate goss testing to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_variant: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image type to isolate goss testing to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_os: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image OS to isolate goss testing to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_platform: Annotated[
                Optional[str],
                typer.Option(
                    show_default=SETTINGS.get_host_architecture(),
                    help="Filters which image build platform to run tests for, e.g. 'linux/amd64'. Image test targets "
                    "incompatible with the given platform(s) will be skipped. Requires a compatible goss binary.",
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
                    help="Path to a build metadata file. If given, attempts to run tests against image artifacts in the file."
                ),
            ] = None,
            clean: Annotated[
                Optional[bool],
                typer.Option(
                    help="Clean up intermediary and temporary files after building. Can be helpful for debugging."
                ),
            ] = True,
        ) -> None:
            """Runs dgoss tests against images in the context path

            \b
            If no options are provided, the command test all images in the project and write test results to the `results/`
            directory in the context path.

            \b
            Images are expected to be available to the local Docker daemon. It is advised to run `build` before running
            dgoss tests.

            \b
            Requires goss and dgoss to be installed on the system. Paths to the binaries can be set with the `GOSS_BIN` and
            `DGOSS_BIN` environment variables if not present in the system PATH.
            """
            # Autoselect host architecture platform if not specified.
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
                clean_temporary=clean,
            )
            c = BakeryConfig.from_context(context, settings)

            if metadata_file:
                c.load_build_metadata_from_file(metadata_file)

            results = plugin.execute(c.base_path, c.targets, platform=platform)

            # Reconstruct a GossJsonReportCollection from results for display
            report_collection = GossJsonReportCollection()
            has_errors = False
            errors = []
            for result in results:
                if result.artifacts and "report" in result.artifacts:
                    report_collection.add_report(result.target, result.artifacts["report"])
                if result.artifacts and "execution_error" in result.artifacts:
                    has_errors = True
                    errors.append(result.artifacts["execution_error"])

            stderr_console.print(report_collection.table())
            if report_collection.test_failures:
                stderr_console.print("-" * 80)
                for uid, failures in report_collection.test_failures.items():
                    stderr_console.print(f"{uid} test failures:", style="error")
                    for failed_result in failures:
                        stderr_console.print(f"  - {failed_result.summary_line_compact}", style="error")
                stderr_console.print(f"\u274c dgoss test(s) failed", style="error")
            if has_errors:
                stderr_console.print("-" * 80)
                for err in errors:
                    stderr_console.print(err, style="error")
                stderr_console.print(f"\u274c dgoss command(s) failed to execute", style="error")
            if report_collection.test_failures or has_errors:
                raise typer.Exit(code=1)

            stderr_console.print(f"\u2705 Tests completed", style="success")

        app.add_typer(dgoss_app, name="dgoss", help="Run Goss tests against container images")

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        platform: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute dgoss tests against the given image targets."""
        suite = DGossSuite(base_path, targets, platform=platform)
        report_collection, errors = suite.run()

        # Build error lookup
        error_list = []
        if errors is not None:
            if isinstance(errors, BakeryToolRuntimeErrorGroup):
                error_list = list(errors.exceptions)
            else:
                error_list = [errors]

        results = []
        for target in targets:
            # Find report for this target
            report = None
            if target.image_name in report_collection:
                target_reports = report_collection[target.image_name]
                if target.uid in target_reports:
                    _, report = target_reports[target.uid]

            # Find error for this target
            target_error = None
            for err in error_list:
                if hasattr(err, "message") and str(target) in err.message:
                    target_error = err
                    break

            exit_code = 0
            if target_error is not None:
                exit_code = getattr(target_error, "exit_code", 1)
            elif report is not None and report.summary.failed_count > 0:
                exit_code = 1

            artifacts = {}
            if report is not None:
                artifacts["report"] = report
            if target_error is not None:
                artifacts["execution_error"] = target_error

            results.append(
                ToolCallResult(
                    exit_code=exit_code,
                    tool_name="dgoss",
                    target=target,
                    stdout="",
                    stderr="",
                    artifacts=artifacts if artifacts else None,
                )
            )

        return results
