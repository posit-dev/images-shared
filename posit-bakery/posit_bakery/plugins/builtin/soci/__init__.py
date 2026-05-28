"""SOCI plugin: convert built images into SOCI-enabled images."""

import logging
from pathlib import Path
from typing import Any

import typer

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.soci.options import SociOptions
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
        """Register the soci CLI commands. Implemented in a later task."""
        soci_app = typer.Typer(no_args_is_help=True)
        app.add_typer(soci_app, name="soci", help=self.description)

    def execute(
        self,
        base_path: Path,
        targets: list[ImageTarget],
        *,
        source_refs: dict[str, str] | None = None,
        dry_run: bool = False,
        standalone: bool = False,
        **kwargs: Any,
    ) -> list[ToolCallResult]:
        """Run SOCI convert workflows against eligible targets.

        ``source_refs`` maps ``target.uid`` -> the temp-registry ref to
        convert (typically produced by the oras index-create phase). In
        standalone mode, refs are filesystem paths instead.

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
                results.append(
                    ToolCallResult(
                        exit_code=1,
                        tool_name="soci",
                        target=target,
                        stdout="",
                        stderr=f"no source ref provided for target '{target.uid}'",
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

        soci_bin = find_soci_bin(base_path)
        ctr_bin = find_ctr_bin(base_path)

        for target, opts, ref in eligible:
            workflow_standalone = opts.standalone if opts.standalone is not None else standalone
            candidates = opts.candidate_namespaces or ["default", "moby"]
            workflow = SociConvertWorkflow(
                soci_bin=soci_bin,
                ctr_bin=ctr_bin,
                image_target=target,
                options=opts,
                source_ref=ref,
                candidate_namespaces=candidates,
                standalone=workflow_standalone,
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
