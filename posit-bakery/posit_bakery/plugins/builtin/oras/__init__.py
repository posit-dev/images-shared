import logging
from pathlib import Path

import typer

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.oras.oras import OrasMergeWorkflow, find_oras_bin
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult

log = logging.getLogger(__name__)


class OrasPlugin(BakeryToolPlugin):
    name: str = "oras"
    description: str = "Merge multi-platform images using ORAS"

    def register_cli(self, app: typer.Typer) -> None:
        """Register the oras CLI commands with the given Typer app."""
        import glob as glob_module
        from typing import Annotated, Optional

        from posit_bakery.cli.common import with_verbosity_flags
        from posit_bakery.config.config import BakeryConfig, BakerySettings
        from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
        from posit_bakery.util import auto_path

        oras_app = typer.Typer(no_args_is_help=True)
        plugin = self

        @oras_app.command()
        @with_verbosity_flags
        def merge(
            metadata_file: Annotated[
                list[Path], typer.Argument(help="Path to input build metadata JSON file(s) to merge.")
            ],
            context: Annotated[
                Path,
                typer.Option(help="The root path to use. Defaults to the current working directory where invoked."),
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
        ):
            """Merge multi-platform images from build metadata files using ORAS.

            \b
            Takes one or more build metadata JSON files (produced by `bakery build --strategy build`)
            and merges platform-specific images into multi-platform manifest indexes.
            """
            settings = BakerySettings(
                dev_versions=DevVersionInclusionEnum.INCLUDE,
                matrix_versions=MatrixVersionInclusionEnum.INCLUDE,
                clean_temporary=False,
                temp_registry=temp_registry,
            )
            config: BakeryConfig = BakeryConfig.from_context(context, settings)

            # Resolve glob patterns in metadata_file arguments
            resolved_files: list[Path] = []
            for file in metadata_file:
                if "*" in str(file) or "?" in str(file) or "[" in str(file):
                    resolved_files.extend(sorted(Path(x).absolute() for x in glob_module.glob(str(file))))
                else:
                    resolved_files.append(file.absolute())
            metadata_file = resolved_files

            log.info(f"Reading targets from {', '.join(f.name for f in metadata_file)}")

            files_ok = True
            loaded_targets: list[str] = []
            for file in metadata_file:
                try:
                    loaded_targets.extend(config.load_build_metadata_from_file(file))
                except Exception as e:
                    log.error(f"Failed to load metadata from file '{file}'")
                    log.error(str(e))
                    files_ok = False
            loaded_targets = list(set(loaded_targets))

            if not files_ok:
                log.error("One or more metadata files are invalid, aborting merge.")
                raise typer.Exit(code=1)

            log.info(f"Found {len(loaded_targets)} targets")
            log.debug(", ".join(loaded_targets))

            results = plugin.execute(config.base_path, config.targets, dry_run=dry_run)
            plugin.results(results)

        app.add_typer(oras_app, name="oras", help="Merge multi-platform images using ORAS")

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        dry_run: bool = False,
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute ORAS merge workflow against the given image targets."""
        # Sort so latest pushes last; Docker Hub displays tags by push-time order.
        targets = sorted(targets, key=lambda t: t.push_sort_key)
        log.info("ORAS merge order: %s", ", ".join(str(t) for t in targets))
        results = []

        for target in targets:
            # Skip targets without merge sources
            if not target.get_merge_sources():
                log.debug(f"Skipping target '{target}' — no merge sources.")
                continue

            # Validate temp_registry
            if not target.settings.temp_registry:
                results.append(
                    ToolCallResult(
                        exit_code=1,
                        tool_name="oras",
                        target=target,
                        stdout="",
                        stderr=f"Cannot merge '{target}': temp_registry must be configured in settings.",
                    )
                )
                continue

            log.info(f"Merging sources for image UID '{target.uid}'")
            workflow = OrasMergeWorkflow.from_image_target(target)
            workflow_result = workflow.run(dry_run=dry_run)

            results.append(
                ToolCallResult(
                    exit_code=0 if workflow_result.success else 1,
                    tool_name="oras",
                    target=target,
                    stdout="",
                    stderr=workflow_result.error or "",
                    artifacts={"workflow_result": workflow_result},
                )
            )

        return results

    def results(self, results: list[ToolCallResult]) -> None:
        """Display ORAS merge results and exit non-zero on failures."""
        from posit_bakery.log import stderr_console

        has_errors = False
        for result in results:
            workflow_result = result.artifacts.get("workflow_result") if result.artifacts else None
            if result.exit_code != 0:
                has_errors = True
                stderr_console.print(
                    f"Error merging '{result.target}': {result.stderr}",
                    style="error",
                )
            elif workflow_result:
                log.info(f"Merged '{result.target}' -> {', '.join(workflow_result.destinations)}")

        if has_errors:
            stderr_console.print("❌ ORAS merge(s) failed", style="error")
            raise typer.Exit(code=1)

        stderr_console.print("✅ ORAS merge completed", style="success")
