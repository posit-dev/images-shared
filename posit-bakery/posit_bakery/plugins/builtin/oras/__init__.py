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
        # CLI registration implemented in Task 3
        pass

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        platform: str | None = None,
        **kwargs,
    ) -> list[ToolCallResult]:
        """Execute ORAS merge workflow against the given image targets."""
        dry_run = kwargs.get("dry_run", False)
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

    def display_results(self, results: list[ToolCallResult]) -> None:
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
                log.info(
                    f"Merged '{result.target}' -> {', '.join(workflow_result.destinations)}"
                )

        if has_errors:
            stderr_console.print("\u274c ORAS merge(s) failed", style="error")
            raise typer.Exit(code=1)

        stderr_console.print("\u2705 ORAS merge completed", style="success")
