"""SOCI CLI integration module."""

import logging
import re
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from posit_bakery.error import BakeryToolRuntimeError
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
