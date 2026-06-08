"""SOCI plugin: convert built images into SOCI-enabled images."""

import logging
from pathlib import Path
from typing import Any

import typer

from posit_bakery.error import BakeryToolNotFoundError
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.soci.options import SociOptions
from posit_bakery.plugins.builtin.oras.oras import find_oras_bin
from posit_bakery.plugins.builtin.soci.soci import (
    SociConvertWorkflow,
    find_ctr_bin,
    find_soci_bin,
)
from posit_bakery.plugins.protocol import BakeryToolPlugin, ToolCallResult

log = logging.getLogger(__name__)


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


class SociPlugin(BakeryToolPlugin):
    name: str = "soci"
    description: str = "Convert images to SOCI-enabled images"
    tool_options_class = SociOptions

    def register_cli(self, app: typer.Typer) -> None:
        """Register the soci CLI commands."""
        import glob as glob_module
        from typing import Annotated, Optional

        from posit_bakery.cli.common import with_verbosity_flags
        from posit_bakery.config.config import BakeryConfig, BakerySettings
        from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
        from posit_bakery.util import auto_path

        soci_app = typer.Typer(no_args_is_help=True)
        plugin = self

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
            standalone: Annotated[
                bool,
                typer.Option(help="Run soci convert in standalone (no-containerd) mode."),
            ] = False,
            dry_run: Annotated[
                bool,
                typer.Option(help="Log commands without executing them."),
            ] = False,
        ) -> None:
            """Convert images referenced by build-metadata JSON files into SOCI-enabled images.

            \b
            By default, operates against containerd (non-standalone mode).
            Targets without `tool: soci, enabled: true` in bakery.yaml are
            skipped.
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
                dry_run=dry_run,
                standalone=standalone,
            )
            plugin.results(results)

        app.add_typer(soci_app, name="soci", help=self.description)

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        source_refs: dict[str, str] | None = None,
        dry_run: bool = False,
        standalone: bool = True,
        **kwargs: Any,
    ) -> list[ToolCallResult]:
        """Run SOCI convert workflows against eligible targets.

        ``source_refs`` maps ``target.uid`` -> the temp-registry ref to
        convert (typically produced by the oras index-create phase). In
        standalone mode the refs are still registry refs; the OCI image
        layouts that ``soci convert --standalone`` reads and writes are
        internal scratch that the workflow materializes and pushes via oras.

        ``standalone`` selects the containerd-free (oras-based) conversion
        path and defaults to ``True``.

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
                "soci.execute: no targets have SOCI enabled (or no source refs "
                "were provided for the enabled ones); skipping conversion."
            )
            return results

        # Mode is uniform across the run (driven by the CLI). Only the tools an
        # eligible target actually executes need to be present: standalone mode
        # bridges the registry with oras and never touches containerd (ctr),
        # while the containerd-backed path uses ctr but not oras. soci is used
        # in both modes.
        needs_containerd = not standalone
        needs_standalone = standalone

        def resolve_bin(finder: Any, fallback: str, *, required: bool) -> str:
            # A tool only has to resolve when it will actually be executed:
            # a dry run executes nothing, and a tool no eligible target uses
            # (e.g. ctr in standalone mode) is never invoked. In those cases
            # fall back to the bare name purely for any logged command. When
            # the tool resolves we keep its real path so output stays accurate.
            # A tool a real run needs but cannot find is still a hard error.
            try:
                return finder(base_path)
            except BakeryToolNotFoundError:
                if dry_run or not required:
                    return fallback
                raise

        soci_bin = resolve_bin(find_soci_bin, "soci", required=True)
        ctr_bin = resolve_bin(find_ctr_bin, "ctr", required=needs_containerd)
        oras_bin = resolve_bin(find_oras_bin, "oras", required=needs_standalone)

        for target, opts, ref in eligible:
            candidates = opts.candidate_namespaces or ["default", "moby"]
            workflow = SociConvertWorkflow(
                soci_bin=soci_bin,
                ctr_bin=ctr_bin,
                oras_bin=oras_bin,
                image_target=target,
                options=opts,
                source_ref=ref,
                candidate_namespaces=candidates,
                standalone=standalone,
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
