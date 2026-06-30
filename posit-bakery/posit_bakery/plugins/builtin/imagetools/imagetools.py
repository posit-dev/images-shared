"""imagetools plugin: merge (ORAS) and SOCI-convert multi-platform images.

Combines the former standalone ``oras`` and ``soci`` plugins. ORAS handles
multi-platform manifest index creation/copy/verify; SOCI converts images into
SOCI-enabled images. The two tools are almost exclusively used together in CI
— the ``bakery ci publish`` orchestration composes ``oras index-create`` →
``soci-convert`` → ``oras index-copy`` → ``oras verify`` — so they live in a
single plugin.

The protocol :meth:`ImageToolsPlugin.execute` / :meth:`ImageToolsPlugin.results`
pair maps to the config-driven SOCI conversion (the operation the publish
orchestration delegates to per target). ORAS merge is exposed via the dedicated
:meth:`merge_execute` / :meth:`merge_results` pair, and the full multi-phase
publish orchestration via :meth:`publish`.
"""

from dataclasses import dataclass
import glob as glob_module
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from posit_bakery.error import BakeryToolNotFoundError
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.imagetools.options import SociOptions
from posit_bakery.plugins.builtin.imagetools.oras import OrasMergeWorkflow, find_oras_bin
from posit_bakery.plugins.builtin.imagetools.soci import SociConvertWorkflow, find_soci_bin
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult

if TYPE_CHECKING:
    from posit_bakery.parallel import CommandRunner

log = logging.getLogger(__name__)


def _resolve_metadata_files(metadata_file: list[Path]) -> list[Path]:
    """Expand any glob patterns in the metadata file arguments."""
    resolved_files: list[Path] = []
    for f in metadata_file:
        s = str(f)
        if "*" in s or "?" in s or "[" in s:
            resolved_files.extend(sorted(Path(x).absolute() for x in glob_module.glob(s)))
        else:
            resolved_files.append(f.absolute())
    return resolved_files


def get_soci_options_for_target(target: ImageTarget) -> SociOptions:
    """Resolve effective SociOptions for the given target, merging
    variant-level options over image-version-parent-level options where
    both exist. Returns a defaulted SociOptions (enabled=False) if no
    soci configuration is present.
    """
    # Local helper to keep the resolution logic in one place.
    image_opts = None
    variant_opts = None
    parent = getattr(target.image_version, "parent", None)
    for opt in getattr(parent, "options", []) or []:
        if isinstance(opt, SociOptions):
            image_opts = opt
            break
    variant = getattr(target, "image_variant", None)
    for opt in getattr(variant, "options", []) or []:
        if isinstance(opt, SociOptions):
            variant_opts = opt
            break
    if variant_opts and image_opts:
        return variant_opts.update(image_opts)
    return variant_opts or image_opts or SociOptions()


@dataclass
class _PublishStage1Result:
    """Outcome of running wait + index-create + (optional) soci-convert for one target."""

    target: ImageTarget
    success: bool = True
    skipped: bool = False
    skip_reason: str | None = None
    temp_ref: str | None = None
    error: str | None = None
    failed_phase: str | None = None


def _run_publish_stage1(
    target: ImageTarget,
    oras_bin: str,
    soci_bin: str,
    dry_run: bool,
    *,
    runner: "CommandRunner | None" = None,
) -> _PublishStage1Result:
    """Wait for a target's own sources, create its temp index, then SOCI-convert it if enabled.

    Runs entirely for one target so it can be wrapped in a ``ShellJob`` and fanned out across
    the parallel executor; one target's failure does not affect any other target. Imports the
    oras/soci workflow classes locally (mirroring the rest of this module) so test patches on
    the source modules are honoured at call time.
    """
    from posit_bakery.error import BakeryToolRuntimeError
    from posit_bakery.plugins.builtin.imagetools.oras import OrasIndexCreateWorkflow, OrasWaitForSourcesWorkflow
    from posit_bakery.plugins.builtin.imagetools.soci import SociConvertWorkflow

    if not target.get_merge_sources():
        return _PublishStage1Result(target=target, skipped=True, skip_reason="no merge sources")
    if not target.settings.temp_registry:
        return _PublishStage1Result(
            target=target,
            success=False,
            failed_phase="create",
            error=f"Cannot publish '{target}': temp_registry not configured.",
        )

    sources = sorted(set(target.get_merge_sources()))
    try:
        wait = OrasWaitForSourcesWorkflow(oras_bin=oras_bin, sources=sources).run(dry_run=dry_run, runner=runner)
    except BakeryToolRuntimeError as e:
        # Non-transient registry error (auth, bad reference, ...) while probing sources:
        # fatal for this target and won't self-heal, but must not escape as an unhandled
        # exception out of a worker thread.
        return _PublishStage1Result(
            target=target,
            success=False,
            failed_phase="wait",
            error=f"Failed while waiting on source digests: {e.dump_stderr() or e}",
        )
    if not wait.success:
        return _PublishStage1Result(
            target=target,
            success=False,
            failed_phase="wait",
            error=f"Source digests not available: {wait.error}",
        )

    create = OrasIndexCreateWorkflow(
        oras_bin=oras_bin,
        image_target=target,
        annotations=target.labels,
    ).run(dry_run=dry_run, runner=runner)
    if not create.success:
        return _PublishStage1Result(target=target, success=False, failed_phase="create", error=create.error)
    temp_ref = create.temp_ref

    soci_opts = get_soci_options_for_target(target)
    if soci_opts.enabled:
        soci = SociConvertWorkflow(
            soci_bin=soci_bin,
            oras_bin=oras_bin,
            image_target=target,
            options=soci_opts,
            source_ref=temp_ref,
        ).run(dry_run=dry_run, runner=runner)
        if not soci.success:
            return _PublishStage1Result(target=target, success=False, failed_phase="soci", error=soci.error)
        temp_ref = soci.destination_ref

    return _PublishStage1Result(target=target, temp_ref=temp_ref)


class ImageToolsPlugin(BakeryToolPlugin):
    name: str = "imagetools"
    description: str = "Merge and SOCI-convert multi-platform images (ORAS + SOCI)"
    tool_options_class = SociOptions

    def register_cli(self, app: typer.Typer) -> None:
        """Register the imagetools CLI commands.

        Canonical group is ``bakery imagetools`` with ``merge`` and
        ``soci-convert`` subcommands. The former ``bakery oras`` and
        ``bakery soci`` groups are preserved as hidden back-compat aliases.
        """
        from typing import Annotated, Optional

        from posit_bakery.cli.common import with_verbosity_flags
        from posit_bakery.config.config import BakeryConfig, BakerySettings
        from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
        from posit_bakery.util import auto_path

        plugin = self

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

            metadata_file = _resolve_metadata_files(metadata_file)
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

            results = plugin.merge_execute(config.base_path, config.targets, dry_run=dry_run)
            plugin.merge_results(results)

        @with_verbosity_flags
        def soci_convert(
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

            metadata_file = _resolve_metadata_files(metadata_file)
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
                dry_run=dry_run,
            )
            plugin.results(results)

        # Canonical group: `bakery imagetools merge` / `bakery imagetools soci-convert`.
        imagetools_app = typer.Typer(no_args_is_help=True)
        imagetools_app.command(name="merge")(merge)
        imagetools_app.command(name="soci-convert")(soci_convert)
        app.add_typer(imagetools_app, name="imagetools", help=self.description)

        # Hidden back-compat aliases for the former standalone plugin groups.
        oras_app = typer.Typer(no_args_is_help=True)
        oras_app.command(name="merge")(merge)
        app.add_typer(oras_app, name="oras", hidden=True, help="Deprecated alias for `bakery imagetools merge`.")

        soci_app = typer.Typer(no_args_is_help=True)
        soci_app.command(name="convert")(soci_convert)
        app.add_typer(soci_app, name="soci", hidden=True, help="Deprecated alias for `bakery imagetools soci-convert`.")

    # ------------------------------------------------------------------
    # SOCI conversion (protocol execute/results)
    # ------------------------------------------------------------------
    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        source_refs: dict[str, str] | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> list[ToolCallResult]:
        """Run SOCI convert workflows against eligible targets.

        ``source_refs`` maps ``target.uid`` -> the temp-registry ref to
        convert (typically produced by the oras index-create phase). The refs
        are registry refs; the OCI image layouts that ``soci convert
        --standalone`` reads and writes are internal scratch that the workflow
        materializes and pushes via oras.

        Conversion always runs in standalone (containerd-free, oras-based)
        mode.

        Targets whose resolved SociOptions has ``enabled=False`` are
        skipped with a ``skipped=True`` artifact entry.
        """
        source_refs = source_refs or {}

        eligible: list[tuple[ImageTarget, SociOptions, str]] = []
        results: list[ToolCallResult] = []
        for target in targets:
            opts = get_soci_options_for_target(target)
            if not opts.enabled:
                results.append(
                    ToolCallResult(
                        exit_code=0,
                        tool_name="soci",
                        target=target,
                        stdout="",
                        stderr="",
                        artifacts={"skipped": True, "reason": "soci.enabled is false"},
                    )
                )
                continue
            ref = source_refs.get(target.uid)
            if not ref:
                # SOCI is enabled for this target but it is not part of the
                # current run — no source ref was produced for it (e.g. it has
                # no merge sources / build metadata in the provided metadata,
                # as happens for the other versions and dev streams when
                # publishing a single set of files). There is nothing to
                # convert, so skip it like a disabled target rather than
                # reporting a spurious conversion failure.
                results.append(
                    ToolCallResult(
                        exit_code=0,
                        tool_name="soci",
                        target=target,
                        stdout="",
                        stderr="",
                        artifacts={"skipped": True, "reason": "no source ref provided for this run"},
                    )
                )
                continue
            eligible.append((target, opts, ref))

        if not eligible:
            log.info(
                "imagetools soci convert: no targets have SOCI enabled (or no source refs "
                "were provided for the enabled ones); skipping conversion."
            )
            return results

        # Standalone conversion bridges the registry with oras and never
        # touches containerd; both soci and oras must be present.
        def resolve_bin(finder: Any, fallback: str) -> str:
            # A tool only has to resolve when it will actually be executed: a
            # dry run executes nothing, so fall back to the bare name purely
            # for any logged command. When the tool resolves we keep its real
            # path so output stays accurate. A tool a real run needs but cannot
            # find is still a hard error.
            try:
                return finder(base_path)
            except BakeryToolNotFoundError:
                if dry_run:
                    return fallback
                raise

        soci_bin = resolve_bin(find_soci_bin, "soci")
        oras_bin = resolve_bin(find_oras_bin, "oras")

        for target, opts, ref in eligible:
            workflow = SociConvertWorkflow(
                soci_bin=soci_bin,
                oras_bin=oras_bin,
                image_target=target,
                options=opts,
                source_ref=ref,
            )
            wf_result = workflow.run(dry_run=dry_run)
            results.append(
                ToolCallResult(
                    exit_code=0 if wf_result.success else 1,
                    tool_name="soci",
                    target=target,
                    stdout="",
                    stderr=wf_result.error or "",
                    artifacts={"workflow_result": wf_result},
                )
            )

        return results

    def results(self, results: list[ToolCallResult]) -> None:
        """Display SOCI conversion results and raise typer.Exit(1) on failure."""
        from posit_bakery.log import stderr_console

        has_errors = False
        for r in results:
            artifacts = r.artifacts or {}
            if artifacts.get("skipped"):
                log.info(f"SOCI skipped for {r.target}: {artifacts.get('reason')}")
                continue
            wf = artifacts.get("workflow_result")
            if r.exit_code != 0:
                has_errors = True
                stderr_console.print(
                    f"SOCI convert failed for '{r.target}': {r.stderr}",
                    style="error",
                )
            elif wf:
                log.info(f"SOCI converted '{r.target}' -> {wf.destination_ref}")

        if has_errors:
            stderr_console.print("❌ SOCI conversion(s) failed", style="error")
            raise typer.Exit(code=1)

        stderr_console.print("✅ SOCI conversion(s) completed", style="success")

    # ------------------------------------------------------------------
    # ORAS merge
    # ------------------------------------------------------------------
    def merge_execute(
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

    def merge_results(self, results: list[ToolCallResult]) -> None:
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

    # ------------------------------------------------------------------
    # Publish orchestration (migrated from `bakery ci publish`)
    # ------------------------------------------------------------------
    def publish(
        self,
        metadata_file: list[Path],
        context: Path,
        *,
        image_name: str | None = None,
        temp_registry: str | None = None,
        dry_run: bool = False,
        dev_channel: Any = None,
        dev_spec: Any = None,
        jobs: int | None = None,
    ) -> None:
        """Publish multi-platform images by composing wait -> index-create -> soci-convert ->
        index-copy -> verify.

        Targets are converted into SOCI-enabled images only when their resolved SOCI options
        have ``enabled: true`` (set via ``soci`` tool options on the image variant). Targets
        without SOCI enabled pass through that step untouched. Conversion runs in standalone
        (no containerd) mode via oras.

        Stage 1 (wait for that target's own sources, then index-create, then soci-convert)
        runs concurrently across targets, bounded by ``jobs`` (falls back to
        ``SETTINGS.max_concurrency``); one target's failure does not block any other target.
        Stage 2 (index-copy, the actual registry push) is sequential and runs in
        ``push_sort_key`` order so registries that display tags by push time (e.g. Docker
        Hub) still show the latest version as most recent. Stage 3 (verify) is sequential and
        read-only.

        Temporary indexes are left in place; they are cleaned up out-of-band by the clean.yml
        workflow (``bakery clean temp-registry``) rather than deleted here.

        Raises ``typer.Exit(1)`` if any target failed Stage 1, or if any index-copy or verify
        failed.
        """
        from posit_bakery.config import BakeryConfig
        from posit_bakery.config.config import BakeryConfigFilter, BakerySettings
        from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
        from posit_bakery.parallel import ParallelShellExecutor, ShellJob, resolve_max_workers

        # Imported locally to mirror existing patterns and keep test seams (patch on the
        # source module) working at call time.
        from posit_bakery.plugins.builtin.imagetools.oras import (
            OrasIndexCopyWorkflow,
            OrasIndexVerifyWorkflow,
            find_oras_bin,
        )

        settings = BakerySettings(
            filter=BakeryConfigFilter(image_name=image_name),
            dev_versions=DevVersionInclusionEnum.INCLUDE,
            dev_channel=dev_channel,
            dev_spec=dev_spec,  # type: ignore[arg-type]  # typer requires str annotation; parse_dev_spec callback delivers DevBuildSpec at runtime
            matrix_versions=MatrixVersionInclusionEnum.INCLUDE,
            clean_temporary=False,
            temp_registry=temp_registry,
        )
        config: BakeryConfig = BakeryConfig.from_context(context, settings)

        metadata_file = _resolve_metadata_files(metadata_file)

        log.info(f"Reading targets from {', '.join(f.name for f in metadata_file)}")

        files_ok = True
        loaded_targets: list[str] = []
        for f in metadata_file:
            try:
                loaded_targets.extend(config.load_build_metadata_from_file(f))
            except Exception as e:
                log.error(f"Failed to load metadata from file '{f}': {e}")
                files_ok = False
        if not files_ok:
            raise typer.Exit(code=1)

        loaded_targets = list(set(loaded_targets))  # Deduplicate targets in case of overlap across files
        log.info(f"Found {len(loaded_targets)} targets")
        log.debug(", ".join(loaded_targets))

        oras_bin = find_oras_bin(config.base_path)
        try:
            soci_bin = find_soci_bin(config.base_path)
        except BakeryToolNotFoundError:
            # A real run needs soci but cannot find it is still a hard error; a dry run
            # executes nothing, so fall back to the bare name purely for logged commands.
            if not dry_run:
                raise
            soci_bin = "soci"

        # Act only on targets that were actually present in the provided metadata
        # files, not every target defined in the config. Publishing a single set of
        # files (e.g. one version / dev stream) otherwise drags in every other
        # version and variant, which each phase then has to re-skip individually.
        # The UIDs in loaded_targets all originate from config.targets, so the
        # lookups always resolve.
        targets = sorted(
            (t for uid in loaded_targets if (t := config.get_image_target_by_uid(uid)) is not None),
            key=lambda t: t.push_sort_key,
        )

        # Stage 1: wait for each target's own sources, then index-create, then soci-convert.
        # Runs concurrently across targets; one target's failure is isolated to it.
        shell_jobs = [
            ShellJob(
                key=t.uid,
                label=str(t),
                run=lambda runner, t=t: _run_publish_stage1(t, oras_bin, soci_bin, dry_run, runner=runner),
            )
            for t in targets
        ]
        executor = ParallelShellExecutor(max_workers=resolve_max_workers(jobs, len(shell_jobs)))
        job_results = executor.run_jobs(shell_jobs)

        stage1_failed = False
        temp_refs: dict[str, str] = {}
        for jr in job_results:
            if not jr.ok:
                stage1_failed = True
                log.error(f"publish Stage 1 crashed for '{jr.job.display_label}': {jr.exception}")
                continue
            stage1_result: _PublishStage1Result = jr.value
            if stage1_result.skipped:
                log.debug(f"Skipping target '{stage1_result.target}' ({stage1_result.skip_reason}).")
                continue
            if not stage1_result.success:
                stage1_failed = True
                log.error(
                    f"publish Stage 1 failed for '{stage1_result.target}' "
                    f"at phase '{stage1_result.failed_phase}': {stage1_result.error}"
                )
                continue
            temp_refs[stage1_result.target.uid] = stage1_result.temp_ref

        # Stage 2: index copy. Sequential, in push_sort_key order (targets is already sorted
        # that way) -- this is the only stage that must stay ordered, since it is the actual
        # registry push that determines what registries display as "most recent".
        copy_failed = False
        copied_targets: list[ImageTarget] = []
        for t in targets:
            if t.uid not in temp_refs:
                continue
            copy = OrasIndexCopyWorkflow(
                oras_bin=oras_bin,
                image_target=t,
            ).run(source=temp_refs[t.uid], dry_run=dry_run)
            if not copy.success:
                log.error(f"index-copy failed for '{t}': {copy.error}")
                copy_failed = True
            else:
                copied_targets.append(t)

        # Stage 3: verify each final destination tag resolves. Read-only and order-independent,
        # so it stays a simple sequential loop.
        verify_failed = False
        if not dry_run:
            for t in copied_targets:
                verify = OrasIndexVerifyWorkflow(
                    oras_bin=oras_bin,
                    image_target=t,
                ).run(dry_run=dry_run)
                if not verify.success:
                    log.error(f"verification failed for '{t}': {verify.error}")
                    verify_failed = True
                else:
                    log.info(f"Verified '{t}' -> {', '.join(verify.verified)}")

        # The temporary indexes (and any SOCI-converted variants) are intentionally left in
        # place; they are cleaned up out-of-band by the clean.yml workflow (bakery clean
        # temp-registry) rather than deleted here.

        if stage1_failed or copy_failed or verify_failed:
            raise typer.Exit(code=1)
