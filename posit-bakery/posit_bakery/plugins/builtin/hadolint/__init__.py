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
from posit_bakery.plugins.builtin.hadolint.options import HadolintOptions
from posit_bakery.plugins.builtin.hadolint.report import HadolintReportCollection
from posit_bakery.plugins.builtin.hadolint.suite import HadolintSuite
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


class RichHelpPanelEnum(str, Enum):
    """Enum for categorizing options into rich help panels."""

    FILTERS = "Filters"
    HADOLINT = "Hadolint Options"


class HadolintPlugin(BakeryToolPlugin):
    name: str = "hadolint"
    description: str = "Lint Containerfiles using hadolint"
    tool_options_class = HadolintOptions

    def register_cli(self, app: typer.Typer) -> None:
        """Register the hadolint CLI commands with the given Typer app."""
        hadolint_app = typer.Typer(no_args_is_help=True)

        plugin = self

        @hadolint_app.command()
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
                    help="The root path to use. Defaults to the current working directory.",
                ),
            ] = auto_path(),
            image_name: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image name to isolate linting to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_version: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image version to isolate linting to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_variant: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image variant to isolate linting to.",
                    rich_help_panel=RichHelpPanelEnum.FILTERS,
                ),
            ] = None,
            image_os: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="The image OS to isolate linting to.",
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
            failure_threshold: Annotated[
                Optional[str],
                typer.Option(
                    "--failure-threshold",
                    help="Exit with failure if any rule at or above this severity is violated. "
                    "One of: error, warning, info, style, ignore, none.",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = "error",
            ignore: Annotated[
                Optional[list[str]],
                typer.Option(
                    "--ignore",
                    help="Rule code to ignore (can be repeated).",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
            require_label: Annotated[
                Optional[list[str]],
                typer.Option(
                    "--require-label",
                    help="Label to require in format 'name:type' (can be repeated).",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
            no_fail: Annotated[
                Optional[bool],
                typer.Option(
                    "--no-fail",
                    help="Always exit with status 0, even when rule violations are found.",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
            error: Annotated[
                Optional[list[str]],
                typer.Option(
                    "--error",
                    help="Rule code to treat as error (can be repeated).",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
            warning: Annotated[
                Optional[list[str]],
                typer.Option(
                    "--warning",
                    help="Rule code to treat as warning (can be repeated).",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
            info: Annotated[
                Optional[list[str]],
                typer.Option(
                    "--info",
                    help="Rule code to treat as info (can be repeated).",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
            style: Annotated[
                Optional[list[str]],
                typer.Option(
                    "--style",
                    help="Rule code to treat as style (can be repeated).",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
            strict_labels: Annotated[
                Optional[bool],
                typer.Option(
                    "--strict-labels",
                    help="Require labels to match the label schema.",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
            disable_ignore_pragma: Annotated[
                Optional[bool],
                typer.Option(
                    "--disable-ignore-pragma",
                    help="Disable inline hadolint ignore comments.",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
            trusted_registry: Annotated[
                Optional[list[str]],
                typer.Option(
                    "--trusted-registry",
                    help="Trusted Docker registry (can be repeated).",
                    rich_help_panel=RichHelpPanelEnum.HADOLINT,
                ),
            ] = None,
        ) -> None:
            """Runs hadolint against Containerfiles in the context path

            \b
            If no options are provided, the command lints all image Containerfiles in the project and writes
            results to the `results/hadolint/` directory in the context path.

            \b
            Requires hadolint to be installed on the system. The path to the binary can be set with the
            `HADOLINT_PATH` environment variable if not present in the system PATH.
            """
            settings = BakerySettings(
                filter=BakeryConfigFilter(
                    image_name=image_name,
                    image_version=re.escape(image_version) if image_version else None,
                    image_variant=image_variant,
                    image_os=image_os,
                    image_platform=[],
                ),
                dev_versions=dev_versions,
                matrix_versions=matrix_versions,
            )
            c = BakeryConfig.from_context(context, settings)

            # Build options override from CLI flags
            override_dict = {}
            if error or warning or info or style:
                if error:
                    override_dict["error"] = error
                if warning:
                    override_dict["warning"] = warning
                if info:
                    override_dict["info"] = info
                if style:
                    override_dict["style"] = style

            label_schema = None
            if require_label:
                label_schema = {}
                for label_spec in require_label:
                    name, sep, schema_type = label_spec.partition(":")
                    if sep:
                        label_schema[name] = schema_type
                    else:
                        label_schema[name] = "text"

            options_override = HadolintOptions(
                failureThreshold=failure_threshold,
                ignored=ignore,
                labelSchema=label_schema,
                noFail=no_fail,
                override=override_dict if override_dict else None,
                strictLabels=strict_labels,
                disableIgnorePragma=disable_ignore_pragma,
                trustedRegistries=trusted_registry,
            )

            results = plugin.execute(c.base_path, c.targets, options_override=options_override)
            plugin.results(results)

        app.add_typer(hadolint_app, name="hadolint", help="Lint Containerfiles using hadolint")

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        options_override: HadolintOptions | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute hadolint against the given image targets."""
        suite = HadolintSuite(base_path, targets, options_override=options_override)
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
            elif report is not None and report.error_count > 0:
                exit_code = 1

            artifacts = {}
            if report is not None:
                artifacts["report"] = report
            if target_error is not None:
                artifacts["execution_error"] = target_error

            results.append(
                ToolCallResult(
                    exit_code=exit_code,
                    tool_name="hadolint",
                    target=target,
                    stdout="",
                    stderr="",
                    artifacts=artifacts if artifacts else None,
                )
            )

        return results

    def results(self, results: list[ToolCallResult]) -> None:
        """Display hadolint results and raise typer.Exit(1) on failures."""
        report_collection = HadolintReportCollection()
        has_errors = False
        errors = []
        for result in results:
            if result.artifacts and "report" in result.artifacts:
                report_collection.add_report(result.target, result.artifacts["report"])
            if result.artifacts and "execution_error" in result.artifacts:
                has_errors = True
                errors.append(result.artifacts["execution_error"])

        # Summary table
        stderr_console.print(report_collection.table())

        # Detailed results by image and UID
        if report_collection.has_issues:
            stderr_console.print("-" * 80)
            for image_name, targets in report_collection.items():
                stderr_console.print(f"=== {image_name} ===", style="bold")
                for uid, (target, report) in targets.items():
                    stderr_console.print(f"--- {uid} ---")
                    stderr_console.print(f"  Containerfile: {report.containerfile}")
                    if report.total_count == 0:
                        stderr_console.print("  No issues found.", style="green3")
                    else:
                        for issue in report.results:
                            level_style = {
                                "error": "bright_red",
                                "warning": "yellow",
                                "info": "bright_blue",
                                "style": "bright_black",
                            }.get(issue.level, "")
                            stderr_console.print(
                                f"  {issue.code} {issue.level} line {issue.line}: {issue.message}",
                                style=level_style,
                            )

        # Execution errors
        if has_errors:
            stderr_console.print("-" * 80)
            for err in errors:
                stderr_console.print(err, style="error")
            stderr_console.print("\u274c hadolint command(s) failed to execute", style="error")

        # Determine exit
        has_failures = any(r.exit_code != 0 for r in results)
        if has_failures or has_errors:
            raise typer.Exit(code=1)

        stderr_console.print("\u2705 Linting completed", style="success")
