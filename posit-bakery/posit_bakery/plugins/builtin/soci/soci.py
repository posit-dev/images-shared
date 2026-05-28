"""SOCI CLI integration module."""

import logging
import re
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.soci.options import SociOptions
from posit_bakery.util import find_bin

log = logging.getLogger(__name__)


def find_soci_bin(context: Path) -> str:
    """Resolve a path or PATH-resident name for the soci binary.

    :param context: Project context to search for the binary in.
    :return: Path to the soci binary, or the bare name "soci" when it
        resolves through PATH.
    :raises BakeryToolNotFoundError: If soci cannot be found.
    """
    return find_bin(context, "soci", "SOCI_PATH") or "soci"


class SociCommand(BaseModel, ABC):
    """Base class for soci CLI invocations."""

    soci_bin: Annotated[str, Field(description="Path to the soci binary.")]
    containerd_address: Annotated[
        str | None,
        Field(default=None, description="containerd GRPC address. None => soci default."),
    ]
    containerd_namespace: Annotated[
        str,
        Field(default="default", description="containerd namespace for commands."),
    ]
    standalone: Annotated[
        bool,
        Field(default=False, description="Run without containerd (file-to-file mode)."),
    ]

    @property
    @abstractmethod
    def command(self) -> list[str]:
        """Return the full command to execute."""
        ...

    def run(self, dry_run: bool = False) -> subprocess.CompletedProcess:
        """Execute the soci command.

        :param dry_run: If True, log the command without executing it.
        :return: The completed process result.
        :raises BakeryToolRuntimeError: On non-zero exit.
        """
        cmd = self.command
        log.debug(f"Executing soci command: {' '.join(cmd)}")

        if dry_run:
            log.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise BakeryToolRuntimeError(
                message="soci command failed",
                tool_name="soci",
                cmd=cmd,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )

        return result


class SociConvert(SociCommand):
    """`soci convert` wrapper.

    Source and destination are image refs in non-standalone mode and
    filesystem paths (OCI archive or directory) in standalone mode.
    """

    source: Annotated[str, Field(description="Source image ref or OCI-layout path.")]
    destination: Annotated[str, Field(description="Destination image ref or OCI-layout path.")]
    platforms: Annotated[
        list[str] | None,
        Field(default=None, description="Platforms to convert. None => --all-platforms."),
    ]
    span_size: Annotated[int | None, Field(default=None, description="zTOC span size in bytes.")]
    min_layer_size: Annotated[int | None, Field(default=None, description="Minimum indexed layer size.")]
    prefetch_files: Annotated[list[str], Field(default_factory=list, description="Files to prefetch.")]
    optimizations: Annotated[list[str], Field(default_factory=list, description="Optional optimizations.")]
    force: Annotated[bool, Field(default=False, description="Force regeneration of existing zTOCs.")]
    output_format: Annotated[
        Literal["oci-archive", "oci-dir"],
        Field(default="oci-archive", description="Standalone-mode output layout (ignored otherwise)."),
    ]

    @property
    def command(self) -> list[str]:
        cmd: list[str] = [self.soci_bin]
        if self.containerd_address:
            cmd += ["--address", self.containerd_address]
        cmd += ["--namespace", self.containerd_namespace, "convert"]
        if self.standalone:
            cmd += ["--standalone", "--format", self.output_format]
        if self.platforms:
            for p in self.platforms:
                cmd += ["--platform", p]
        else:
            cmd.append("--all-platforms")
        if self.span_size is not None:
            cmd += ["--span-size", str(self.span_size)]
        if self.min_layer_size is not None:
            cmd += ["--min-layer-size", str(self.min_layer_size)]
        for f in self.prefetch_files:
            cmd += ["--prefetch-file", f]
        for o in self.optimizations:
            cmd += ["--optimizations", o]
        if self.force:
            cmd.append("--force")
        cmd += [self.source, self.destination]
        return cmd


class SociPush(SociCommand):
    """`soci push` wrapper: upload SOCI-enabled artifacts from containerd."""

    image_ref: Annotated[str, Field(description="Image ref to push.")]
    platforms: Annotated[
        list[str] | None,
        Field(default=None, description="Platforms to push. None => --all-platforms."),
    ]
    existing_index: Annotated[
        Literal["warn", "skip", "allow"],
        Field(default="warn", description="Behavior when a SOCI index already exists for the ref."),
    ]
    plain_http: Annotated[bool, Field(default=False, description="Allow plain HTTP registry connections.")]
    max_concurrent_uploads: Annotated[
        int | None,
        Field(default=None, description="Max concurrent uploads. SOCI default if None."),
    ]

    @property
    def command(self) -> list[str]:
        cmd: list[str] = [self.soci_bin]
        if self.containerd_address:
            cmd += ["--address", self.containerd_address]
        cmd += ["--namespace", self.containerd_namespace, "push"]
        if self.platforms:
            for p in self.platforms:
                cmd += ["--platform", p]
        else:
            cmd.append("--all-platforms")
        cmd += ["--existing-index", self.existing_index]
        if self.plain_http:
            cmd.append("--plain-http")
        if self.max_concurrent_uploads is not None:
            cmd += ["--max-concurrent-uploads", str(self.max_concurrent_uploads)]
        cmd.append(self.image_ref)
        return cmd


IMAGE_NOT_FOUND_RE = re.compile(rb'image "[^"]+": not found')
"""Matches soci's canonical "image not found" error so namespace probes can
distinguish a missing image from a real error."""


def find_ctr_bin(context: Path) -> str:
    """Resolve a path or PATH-resident name for the ctr binary.

    :param context: Project context to search for the binary in.
    :return: Path to the ctr binary, or the bare name "ctr" when it
        resolves through PATH.
    :raises BakeryToolNotFoundError: If ctr cannot be found.
    """
    return find_bin(context, "ctr", "CTR_PATH") or "ctr"


class ContainerdImagePull(BaseModel):
    """`ctr image pull` wrapper.

    Not a SociCommand because it shells out to containerd's CLI rather than
    soci itself, but the surface is similar enough to keep it in this module
    (it only exists to serve the SOCI workflow).
    """

    ctr_bin: Annotated[str, Field(description="Path to the ctr binary.")]
    containerd_address: Annotated[str | None, Field(default=None)]
    containerd_namespace: Annotated[str, Field(default="default")]
    image_ref: Annotated[str, Field(description="Image ref to pull.")]
    all_platforms: Annotated[
        bool,
        Field(
            default=False,
            description="Pass --all-platforms; default ctr behavior is multi-platform without it, but explicit is safer.",
        ),
    ]

    @property
    def command(self) -> list[str]:
        cmd: list[str] = [self.ctr_bin]
        if self.containerd_address:
            cmd += ["--address", self.containerd_address]
        cmd += ["--namespace", self.containerd_namespace, "image", "pull"]
        if self.all_platforms:
            cmd.append("--all-platforms")
        cmd.append(self.image_ref)
        return cmd

    def run(self, dry_run: bool = False) -> subprocess.CompletedProcess:
        """Execute the ctr image pull command.

        :param dry_run: If True, log the command without executing it.
        :return: The completed process result.
        :raises BakeryToolRuntimeError: On non-zero exit.
        """
        cmd = self.command
        log.debug(f"Executing ctr command: {' '.join(cmd)}")

        if dry_run:
            log.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise BakeryToolRuntimeError(
                message="ctr image pull failed",
                tool_name="ctr",
                cmd=cmd,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )

        return result


class SociConvertWorkflowResult(BaseModel):
    success: Annotated[bool, Field(description="Whether the workflow completed successfully.")]
    destination_ref: Annotated[str | None, Field(default=None, description="SOCI-enabled destination ref.")]
    resolved_namespace: Annotated[
        str | None, Field(default=None, description="Containerd namespace that held the source.")
    ]
    error: Annotated[str | None, Field(default=None, description="Error message if the workflow failed.")]


class SociConvertWorkflow(BaseModel):
    """Pull a source ref into containerd, convert it to SOCI, and push back."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    soci_bin: Annotated[str, Field(description="Path to the soci binary.")]
    ctr_bin: Annotated[str, Field(description="Path to the ctr binary.")]
    image_target: Annotated[ImageTarget, Field(description="The image target.")]
    options: Annotated[SociOptions, Field(description="Per-target SOCI configuration.")]
    source_ref: Annotated[str, Field(description="Temp-registry ref to convert from.")]
    candidate_namespaces: Annotated[
        list[str],
        Field(default_factory=lambda: ["default", "moby"], description="Namespaces to probe."),
    ]
    standalone: Annotated[bool, Field(default=False, description="Standalone (no-containerd) mode.")]

    @property
    def destination_ref(self) -> str:
        return f"{self.source_ref}-soci"

    def _build_convert(self, namespace: str) -> SociConvert:
        return SociConvert(
            soci_bin=self.soci_bin,
            containerd_namespace=namespace,
            standalone=self.standalone,
            source=self.source_ref,
            destination=self.destination_ref,
            platforms=self.options.platforms,
            span_size=self.options.span_size,
            min_layer_size=self.options.min_layer_size,
            prefetch_files=self.options.prefetch_files,
            optimizations=self.options.optimizations,
        )

    def _build_push(self, namespace: str) -> SociPush:
        return SociPush(
            soci_bin=self.soci_bin,
            containerd_namespace=namespace,
            image_ref=self.destination_ref,
            platforms=self.options.platforms,
        )

    def run(self, dry_run: bool = False) -> SociConvertWorkflowResult:
        """Materialize source in containerd, convert, push. Probes
        ``candidate_namespaces`` until ctr-pull finds the source image."""
        last_error: str | None = None
        last_ns: str | None = None
        for ns in self.candidate_namespaces:
            last_ns = ns
            try:
                ContainerdImagePull(
                    ctr_bin=self.ctr_bin,
                    containerd_namespace=ns,
                    image_ref=self.source_ref,
                    all_platforms=True,
                ).run(dry_run=dry_run)
            except BakeryToolRuntimeError as e:
                if e.stderr and IMAGE_NOT_FOUND_RE.search(e.stderr):
                    last_error = f'image "{self.source_ref}": not found in namespace "{ns}"'
                    log.debug(last_error)
                    continue
                log.error(f"SOCI workflow: ctr pull failed: {e}")
                return SociConvertWorkflowResult(
                    success=False,
                    destination_ref=self.destination_ref,
                    resolved_namespace=ns,
                    error=e.dump_stderr() or str(e),
                )

            try:
                self._build_convert(ns).run(dry_run=dry_run)
                self._build_push(ns).run(dry_run=dry_run)
            except BakeryToolRuntimeError as e:
                log.error(f"SOCI workflow: convert/push failed in namespace '{ns}': {e}")
                return SociConvertWorkflowResult(
                    success=False,
                    destination_ref=self.destination_ref,
                    resolved_namespace=ns,
                    error=e.dump_stderr() or str(e),
                )

            return SociConvertWorkflowResult(
                success=True,
                destination_ref=self.destination_ref,
                resolved_namespace=ns,
            )

        return SociConvertWorkflowResult(
            success=False,
            destination_ref=self.destination_ref,
            resolved_namespace=last_ns,
            error=last_error or "image not found in any candidate namespace",
        )
