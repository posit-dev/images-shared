"""imagetools plugin: the unified multi-platform publish pipeline (oras + soci).

A single plugin owns the oras and soci tooling. It registers three command groups —
``bakery ci publish`` (via the ci app), ``bakery oras merge``, and ``bakery soci convert`` —
that all run the same pipeline (restricted to the relevant phases). Each target's
create -> soci -> copy -> verify sequence runs as one job on the parallel executor, so
independent targets publish concurrently and every registry command retries-with-backoff on
transient failures (issue #591).
"""

import logging
from pathlib import Path
from typing import Any

import typer

from posit_bakery.error import BakeryToolNotFoundError
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.parallel import (
    JobResult,
    ParallelShellExecutor,
    ShellJob,
    resolve_max_workers,
)
from posit_bakery.plugins.builtin.imagetools import soci as soci_mod
from posit_bakery.plugins.builtin.imagetools.options import SociOptions
from posit_bakery.plugins.builtin.imagetools.oras import find_oras_bin
from posit_bakery.plugins.builtin.imagetools.publish import (
    ALL_PHASES,
    MERGE_PHASES,
    SOCI_PHASES,
    PublishPhase,
    PublishResult,
    PublishWorkflow,
)
from posit_bakery.plugins.builtin.imagetools.retry import DEFAULT_COMMAND_TIMEOUT, DEFAULT_REGISTRY_RETRY
from posit_bakery.plugins.builtin.imagetools.soci import find_soci_bin
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult

log = logging.getLogger(__name__)


def _resolve_bin(finder: Any, base_path: Path, dry_run: bool, fallback: str) -> str:
    """Resolve a tool path, tolerating a missing tool on a dry run (which executes nothing)."""
    try:
        return finder(base_path)
    except BakeryToolNotFoundError:
        if dry_run:
            return fallback
        raise


class ImageToolsPlugin(BakeryToolPlugin):
    name: str = "imagetools"
    description: str = "Publish multi-platform images (oras index + soci convert)"
    # The soci tool options (``tool: soci`` in bakery.yaml) belong to this consolidated plugin.
    tool_options_class = SociOptions

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        source_refs: dict[str, str] | None = None,
        phases: frozenset[PublishPhase] = ALL_PHASES,
        dry_run: bool = False,
        jobs: int | None = None,
        **kwargs: Any,
    ) -> list[ToolCallResult]:
        """Run the (subset of the) publish pipeline for each target, in parallel.

        :param source_refs: ``target.uid`` -> source ref, used to seed the soci-only path.
        :param phases: Which pipeline phases to run (full publish by default).
        :param jobs: Concurrency override; otherwise BAKERY_MAX_CONCURRENCY / default.
        """
        # Latest pushes last so registries that order tags by push time display it on top.
        targets = sorted(targets, key=lambda t: t.push_sort_key)
        if not targets:
            return []
        source_refs = source_refs or {}

        oras_bin = _resolve_bin(find_oras_bin, base_path, dry_run, "oras")
        needs_soci = PublishPhase.SOCI in phases and any(
            soci_mod.get_soci_options_for_target(t).enabled for t in targets
        )
        soci_bin = _resolve_bin(find_soci_bin, base_path, dry_run, "soci") if needs_soci else "soci"

        shell_jobs: list[ShellJob] = []
        for target in targets:
            workflow = PublishWorkflow(
                image_target=target,
                oras_bin=oras_bin,
                soci_bin=soci_bin,
                source_ref=source_refs.get(target.uid),
            )
            shell_jobs.append(
                ShellJob(
                    key=target.uid,
                    label=str(target),
                    run=lambda runner, wf=workflow: wf.run(runner, phases=phases, dry_run=dry_run),
                    payload=target,
                    retry=DEFAULT_REGISTRY_RETRY,
                    command_timeout=DEFAULT_COMMAND_TIMEOUT,
                )
            )

        def on_result(job_result: JobResult) -> None:
            # Main thread: safe to log. Surface progress per finished target.
            target = job_result.job.payload
            if job_result.exception is not None:
                log.error(f"publish failed for '{target}': {job_result.exception}")
                return
            pr: PublishResult = job_result.value
            if pr.skipped:
                log.debug(f"Skipped '{target}' ({pr.skip_reason}).")
            elif not pr.success:
                log.error(f"{pr.failed_phase} failed for '{target}': {pr.error}")
            else:
                if pr.soci_destination_ref:
                    log.info(f"SOCI converted '{target}' -> {pr.soci_destination_ref}")
                if pr.verified:
                    log.info(f"Verified '{target}' -> {', '.join(pr.verified)}")

        max_workers = resolve_max_workers(jobs, len(shell_jobs))
        executor = ParallelShellExecutor(max_workers=max_workers)
        job_results = executor.run_jobs(shell_jobs, on_result=on_result)
        return [self._to_tool_result(jr) for jr in job_results]

    @staticmethod
    def _to_tool_result(job_result: JobResult) -> ToolCallResult:
        target = job_result.job.payload
        if job_result.exception is not None:
            return ToolCallResult(
                exit_code=1,
                tool_name="imagetools",
                target=target,
                stdout="",
                stderr=str(job_result.exception),
                artifacts={"error": str(job_result.exception)},
            )
        pr: PublishResult = job_result.value
        if pr.skipped:
            return ToolCallResult(
                exit_code=0,
                tool_name="imagetools",
                target=target,
                stdout="",
                stderr="",
                artifacts={"skipped": True, "reason": pr.skip_reason, "publish_result": pr},
            )
        return ToolCallResult(
            exit_code=0 if pr.success else 1,
            tool_name="imagetools",
            target=target,
            stdout="",
            stderr=pr.error or "",
            artifacts={"publish_result": pr},
        )

    def results(self, results: list[ToolCallResult]) -> None:
        """Print a publish summary and raise typer.Exit(1) if any target failed."""
        from posit_bakery.log import stderr_console

        has_errors = False
        for result in results:
            artifacts = result.artifacts or {}
            if artifacts.get("skipped"):
                log.debug(f"imagetools skipped '{result.target}': {artifacts.get('reason')}")
                continue
            if result.exit_code != 0:
                has_errors = True
                stderr_console.print(f"Publish failed for '{result.target}': {result.stderr}", style="error")

        if has_errors:
            stderr_console.print("❌ Publish failed", style="error")
            raise typer.Exit(code=1)

        stderr_console.print("✅ Publish completed", style="success")

    def register_cli(self, app: typer.Typer) -> None:
        """Register ``imagetools publish``, ``oras merge``, and ``soci convert``.

        All three drive :meth:`execute` with the appropriate phase subset; the historical
        ``oras``/``soci`` command groups are preserved even though one plugin now owns them.
        """
        from posit_bakery.cli.ci import publish as ci_publish

        plugin = self

        # `imagetools publish` mirrors `ci publish` without duplicating its metadata-loading.
        imagetools_app = typer.Typer(no_args_is_help=True)
        imagetools_app.command(name="publish")(ci_publish)
        app.add_typer(imagetools_app, name="imagetools", help=self.description)

        app.add_typer(self._build_oras_app(plugin), name="oras", help="Merge multi-platform images using ORAS")
        app.add_typer(self._build_soci_app(plugin), name="soci", help="Convert images to SOCI-enabled images")

    @staticmethod
    def _build_oras_app(plugin: "ImageToolsPlugin") -> typer.Typer:
        import glob as glob_module
        from typing import Annotated, Optional

        from posit_bakery.cli.common import with_verbosity_flags
        from posit_bakery.config.config import BakeryConfig, BakerySettings
        from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
        from posit_bakery.util import auto_path

        oras_app = typer.Typer(no_args_is_help=True)

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

            results = plugin.execute(config.base_path, config.targets, phases=MERGE_PHASES, dry_run=dry_run)
            plugin.results(results)

        return oras_app

    @staticmethod
    def _build_soci_app(plugin: "ImageToolsPlugin") -> typer.Typer:
        import glob as glob_module
        from typing import Annotated, Optional

        from posit_bakery.cli.common import with_verbosity_flags
        from posit_bakery.config.config import BakeryConfig, BakerySettings
        from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
        from posit_bakery.util import auto_path

        soci_app = typer.Typer(no_args_is_help=True)

        @soci_app.command()
        @with_verbosity_flags
        def convert(
            metadata_file: Annotated[list[Path], typer.Argument(help="Path to input build metadata JSON file(s).")],
            context: Annotated[
                Path,
                typer.Option(help="The root path to use. Defaults to the current working directory."),
            ] = auto_path(),
            temp_registry: Annotated[
                Optional[str],
                typer.Option(help="Temporary registry to use for split/merge builds."),
            ] = None,
            dry_run: Annotated[
                bool,
                typer.Option(help="Log commands without executing them."),
            ] = False,
        ) -> None:
            """Convert images referenced by build-metadata JSON files into SOCI-enabled images.

            \b
            Conversion runs in standalone (no-containerd) mode via oras. Targets
            without `tool: soci, enabled: true` in bakery.yaml are skipped.
            """
            settings = BakerySettings(
                dev_versions=DevVersionInclusionEnum.INCLUDE,
                matrix_versions=MatrixVersionInclusionEnum.INCLUDE,
                clean_temporary=False,
                temp_registry=temp_registry,
            )
            config: BakeryConfig = BakeryConfig.from_context(context, settings)

            resolved_files: list[Path] = []
            for f in metadata_file:
                s = str(f)
                if "*" in s or "?" in s or "[" in s:
                    resolved_files.extend(sorted(Path(x).absolute() for x in glob_module.glob(s)))
                else:
                    resolved_files.append(f.absolute())
            metadata_file = resolved_files

            log.info(f"Reading targets from {', '.join(f.name for f in metadata_file)}")
            files_ok = True
            for f in metadata_file:
                try:
                    config.load_build_metadata_from_file(f)
                except Exception as e:
                    log.error(f"Failed to load metadata from file '{f}': {e}")
                    files_ok = False
            if not files_ok:
                raise typer.Exit(code=1)

            # Build source_refs from each target's most recent build metadata.
            source_refs: dict[str, str] = {}
            for t in config.targets:
                if t.build_metadata:
                    latest = max(t.build_metadata, key=lambda m: m.created_at)
                    source_refs[t.uid] = latest.image_ref

            results = plugin.execute(
                config.base_path,
                config.targets,
                source_refs=source_refs,
                phases=SOCI_PHASES,
                dry_run=dry_run,
            )
            plugin.results(results)

        return soci_app
