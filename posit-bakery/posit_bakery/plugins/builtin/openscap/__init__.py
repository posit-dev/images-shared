import logging
from enum import Enum
from pathlib import Path
from typing import Annotated, Optional

import typer

from posit_bakery.build.runner import load_build_metadata_from_file
from posit_bakery.cli.common import normalize_platform, parse_dev_spec, with_verbosity_flags
from posit_bakery.config.config import BakeryConfig
from posit_bakery.config.settings import BakeryConfigFilter, BakerySettings
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.log import stderr_console, stdout_console
from posit_bakery.plugins.builtin.openscap.command import StrategyEnum
from posit_bakery.plugins.builtin.openscap.content import (
    DEFAULT_CONTENT_VERSION,
    datastream_for,
    list_profiles,
    release_zip,
)
from posit_bakery.plugins.builtin.openscap.errors import BakeryOpenSCAPContentError, BakeryOpenSCAPError
from posit_bakery.plugins.builtin.openscap.options import FailOnEnum, OpenSCAPOptions, parse_formats
from posit_bakery.plugins.builtin.openscap.report import OpenSCAPReportCollection, OpenSCAPScanNotRun
from posit_bakery.plugins.builtin.openscap.suite import OpenSCAPSuite
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult
from posit_bakery.settings import SETTINGS
from posit_bakery.targets.selection import exit_if_no_targets, select_targets
from posit_bakery.util import auto_path

log = logging.getLogger(__name__)


class RichHelpPanelEnum(str, Enum):
    FILTERS = "Filters"
    OPENSCAP = "OpenSCAP Options"


class OpenSCAPPlugin(BakeryToolPlugin):
    name: str = "openscap"
    description: str = "Report CIS benchmark compliance of container images with OpenSCAP"
    tool_options_class = OpenSCAPOptions

    def register_cli(self, app: typer.Typer) -> None:
        openscap_app = typer.Typer(no_args_is_help=True)
        plugin = self

        @openscap_app.command()
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
                    help="Which image build platform to scan, e.g. 'linux/amd64'.",
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
            # OpenSCAP options. Defaults are None so an unset flag never masks a bakery.yaml value.
            profile: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Profile short name or full XCCDF ID [default: cis_level1_server]. Overrides bakery.yaml.",
                    rich_help_panel=RichHelpPanelEnum.OPENSCAP,
                ),
            ] = None,
            content_version: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help=f"ComplianceAsCode release [default: {DEFAULT_CONTENT_VERSION}]. Overrides bakery.yaml.",
                    rich_help_panel=RichHelpPanelEnum.OPENSCAP,
                ),
            ] = None,
            datastream: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Path or URL of an SCAP datastream, overriding OS-based selection. Overrides bakery.yaml.",
                    rich_help_panel=RichHelpPanelEnum.OPENSCAP,
                ),
            ] = None,
            tailoring: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Tailoring file path or URL, 'builtin:container' [default] or 'none'. Overrides bakery.yaml.",
                    rich_help_panel=RichHelpPanelEnum.OPENSCAP,
                ),
            ] = None,
            skip_rule: Annotated[
                Optional[list[str]],
                typer.Option(
                    "--skip-rule",
                    show_default=False,
                    help="Rule ID to ignore for gating (repeatable). Overrides bakery.yaml.",
                    rich_help_panel=RichHelpPanelEnum.OPENSCAP,
                ),
            ] = None,
            fail_on: Annotated[
                Optional[FailOnEnum],
                typer.Option(
                    show_default=False,
                    help="Fail when a rule fails at or above this severity [default: none]. Overrides bakery.yaml.",
                    rich_help_panel=RichHelpPanelEnum.OPENSCAP,
                ),
            ] = None,
            output_format: Annotated[
                Optional[str],
                typer.Option(
                    "--format",
                    show_default=False,
                    help="Comma-separated outputs: table,json,markdown,html,xccdf,arf,fix "
                    "[default: table,json,html]. Overrides bakery.yaml.",
                    rich_help_panel=RichHelpPanelEnum.OPENSCAP,
                ),
            ] = None,
            strategy: Annotated[
                StrategyEnum,
                typer.Option(
                    help="How the image filesystem is presented to the scanner.",
                    rich_help_panel=RichHelpPanelEnum.OPENSCAP,
                ),
            ] = StrategyEnum.AUTO,
            scanner_image: Annotated[
                Optional[str],
                typer.Option(
                    show_default=False,
                    help="Image providing `oscap`. Defaults to a scanner image built locally on first use.",
                    rich_help_panel=RichHelpPanelEnum.OPENSCAP,
                ),
            ] = None,
            timeout: Annotated[
                int,
                typer.Option(help="Per-image timeout in seconds.", rich_help_panel=RichHelpPanelEnum.OPENSCAP),
            ] = 600,
        ) -> None:
            """Report CIS benchmark compliance of container images using OpenSCAP.

            \b
            Runs `oscap xccdf eval` in a scanner container against each image target's
            filesystem, mounted read-only. Results are written to `results/openscap/`.

            \b
            Images are expected to be available to the local Docker daemon. It is advised
            to run `build` before running scans. Only Docker is required on the host.
            """
            platform = normalize_platform(image_platform)
            try:
                formats = parse_formats(output_format.split(",")) if output_format else None
            except ValueError as e:
                raise typer.BadParameter(str(e)) from e

            settings = BakerySettings(
                filter=BakeryConfigFilter(
                    image_name=image_name,
                    image_version=image_version,
                    image_variant=image_variant,
                    image_os=image_os,
                    image_platform=[platform],
                ),
                dev_versions=dev_versions,
                dev_spec=dev_spec,  # type: ignore[arg-type]  # parse_dev_spec callback delivers DevBuildSpec
                matrix_versions=matrix_versions,
                latest=latest,
            )
            c = BakeryConfig.from_context(context, settings)

            targets = select_targets(c, settings)
            exit_if_no_targets(targets, settings, context="scan")

            if metadata_file:
                load_build_metadata_from_file(targets, metadata_file)

            try:
                results = plugin.execute(
                    c.base_path,
                    targets,
                    platform=platform,
                    strategy=strategy,
                    scanner_image=scanner_image,
                    timeout=timeout,
                    profile=profile,
                    content_version=content_version,
                    datastream=datastream,
                    tailoring=tailoring,
                    skip_rules=skip_rule or None,
                    fail_on=fail_on,
                    formats=formats,
                )
            except BakeryOpenSCAPError as e:
                stderr_console.print(e, style="error")
                raise typer.Exit(code=1)
            plugin.results(results)

        @openscap_app.command()
        @with_verbosity_flags
        def fetch(
            content_version: Annotated[
                str, typer.Option(help="ComplianceAsCode release to download.")
            ] = DEFAULT_CONTENT_VERSION,
        ) -> None:
            """Download and verify SCAP Security Guide content into the local cache."""
            try:
                path = release_zip(content_version)
            except BakeryOpenSCAPContentError as e:
                stderr_console.print(str(e), style="error")
                raise typer.Exit(code=1)
            stderr_console.print(f"✅ Content cached at {path}", style="success")

        @openscap_app.command()
        @with_verbosity_flags
        def profiles(
            products: Annotated[
                list[str], typer.Argument(help="ComplianceAsCode product IDs, e.g. ubuntu2204 ubuntu2404.")
            ],
            content_version: Annotated[
                str, typer.Option(help="ComplianceAsCode release to inspect.")
            ] = DEFAULT_CONTENT_VERSION,
        ) -> None:
            """List the profiles available for products in a ComplianceAsCode release."""
            try:
                for product in products:
                    ds = datastream_for(product, content_version)
                    found = list_profiles(ds) if ds else []
                    stdout_console.print(f"[bold]{product}[/bold] ({content_version}):")
                    for p in found:
                        stdout_console.print(f"  {p}")
                    if not found:
                        stdout_console.print("  (no profiles)")
            except BakeryOpenSCAPContentError as e:
                stderr_console.print(str(e), style="error")
                raise typer.Exit(code=1)

        app.add_typer(openscap_app, name="openscap", help=self.description)

    def execute(self, base_path: Path, targets: list[ImageTarget], **kwargs) -> list[ToolCallResult]:
        outcomes = OpenSCAPSuite(base_path, targets, **kwargs).run()
        return [
            ToolCallResult(
                exit_code=o.error.exit_code if o.error else 0,
                tool_name=self.name,
                target=o.target,
                stdout="",
                stderr="",
                artifacts={"report": o.result, "status": o.status, "execution_error": o.error},
            )
            for o in outcomes
        ]

    def results(self, results: list[ToolCallResult]) -> None:
        collection = OpenSCAPReportCollection()
        errors = []
        for result in results:
            artifacts = result.artifacts or {}
            report = artifacts.get("report") or OpenSCAPScanNotRun("ERROR", "no result recorded")
            collection.add_report(result.target, report, artifacts.get("status", "ERROR"))
            if artifacts.get("execution_error") is not None:
                errors.append(artifacts["execution_error"])

        if collection:
            stderr_console.print(collection.table())

        if errors:
            stderr_console.print("-" * 80)
            for err in errors:
                stderr_console.print(err, style="error")
            stderr_console.print("❌ OpenSCAP scan(s) failed or breached the configured gate", style="error")
            raise typer.Exit(code=1)

        stderr_console.print("✅ Scans completed", style="success")
