"""SOCI CLI integration module."""

import json
import logging
import os
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from posit_bakery.error import BakeryError, BakeryToolRuntimeError
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.oras.oras import OrasCopy
from posit_bakery.plugins.builtin.soci.options import SociOptions
from posit_bakery.util import find_bin

log = logging.getLogger(__name__)


class SociPrivilegeError(BakeryError):
    """Raised when SOCI containerd mode needs root but cannot elevate without
    prompting the user for a password."""


def resolve_sudo_prefix(*, dry_run: bool = False) -> list[str]:
    """Resolve the command prefix that runs containerd-touching commands as root.

    ``ctr image pull``, ``soci convert``, and ``soci push`` all talk to
    containerd's root-owned socket. This returns the prefix to prepend to those
    commands:

    - ``[]`` when already running as root.
    - ``["sudo", "-n"]`` when sudo is available without a prompt (NOPASSWD or a
      cached credential); ``-n`` guarantees no interactive prompt.

    On a real run it raises :class:`SociPrivilegeError` when sudo would prompt,
    so the user is never asked for a password mid-run. On a dry run it never
    raises and returns the best-effort prefix purely so logged commands are
    accurate.

    :param dry_run: When True, never raise; return ``["sudo", "-n"]`` for the
        non-root case so the logged commands stay accurate.
    :return: The prefix list to prepend to containerd commands.
    :raises SociPrivilegeError: On a real run when not root and sudo would prompt.
    """
    if os.geteuid() == 0:
        return []
    passwordless = subprocess.run(["sudo", "-n", "true"], capture_output=True).returncode == 0
    if passwordless:
        return ["sudo", "-n"]
    if dry_run:
        return ["sudo", "-n"]
    raise SociPrivilegeError(
        "SOCI containerd mode needs root to talk to containerd. "
        "Re-run as `sudo bakery ...`, or use `--soci-mode standalone`."
    )


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
    sudo: Annotated[
        bool,
        Field(default=False, description="Prefix the command with `sudo -n` (containerd needs root)."),
    ]

    @property
    def _sudo_prefix(self) -> list[str]:
        return ["sudo", "-n"] if self.sudo else []

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
        cmd: list[str] = [*self._sudo_prefix, self.soci_bin]
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
        cmd: list[str] = [*self._sudo_prefix, self.soci_bin]
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
    sudo: Annotated[
        bool,
        Field(default=False, description="Prefix the command with `sudo -n` (containerd needs root)."),
    ]

    @property
    def command(self) -> list[str]:
        cmd: list[str] = ["sudo", "-n"] if self.sudo else []
        cmd.append(self.ctr_bin)
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
    oras_bin: Annotated[str, Field(description="Path to the oras binary (used in standalone mode).")]
    image_target: Annotated[ImageTarget, Field(description="The image target.")]
    options: Annotated[SociOptions, Field(description="Per-target SOCI configuration.")]
    source_ref: Annotated[str, Field(description="Temp-registry ref to convert from.")]
    standalone: Annotated[bool, Field(default=False, description="Standalone (no-containerd) mode.")]
    sudo: Annotated[
        bool,
        Field(default=False, description="Prefix containerd commands with `sudo -n` (resolved once per run)."),
    ]

    @property
    def destination_ref(self) -> str:
        """SOCI-enabled destination ref. A registry ref in both modes; in
        standalone mode the on-disk OCI layouts are internal scratch and are
        pushed here at the end via oras."""
        return f"{self.source_ref}-soci"

    def _build_convert(
        self,
        namespace: str,
        *,
        source: str | None = None,
        destination: str | None = None,
        output_format: Literal["oci-archive", "oci-dir"] = "oci-archive",
    ) -> SociConvert:
        return SociConvert(
            soci_bin=self.soci_bin,
            containerd_namespace=namespace,
            standalone=self.standalone,
            source=source if source is not None else self.source_ref,
            destination=destination if destination is not None else self.destination_ref,
            platforms=self.options.platforms,
            span_size=self.options.span_size,
            min_layer_size=self.options.min_layer_size,
            prefetch_files=self.options.prefetch_files,
            optimizations=self.options.optimizations,
            output_format=output_format,
            sudo=self.sudo and not self.standalone,
        )

    @staticmethod
    def _read_converted_digest(layout: Path) -> str:
        """Return the digest of the top-level manifest in a converted OCI
        layout. soci writes the converted image to ``index.json`` without a
        tag, so the only way to reference it for the push back is by digest."""
        index = json.loads((layout / "index.json").read_text())
        return index["manifests"][0]["digest"]

    def _run_standalone(self, dry_run: bool = False) -> SociConvertWorkflowResult:
        """Pull the source ref into an OCI layout, convert it to SOCI with
        ``soci convert --standalone``, and push the converted layout back to
        the registry — all without containerd.

        oras bridges the registry on both ends: ``--to-oci-layout`` to
        materialize the source as an OCI layout, ``--from-oci-layout`` to push
        the converted result. The scratch layouts are removed afterward.
        """
        scratch = Path(tempfile.mkdtemp(prefix="soci-standalone-"))
        src_layout = scratch / "src"
        out_layout = scratch / "out"
        try:
            # 1. registry -> OCI layout. The layout tag is arbitrary; soci
            #    reads the whole layout.
            OrasCopy(
                oras_bin=self.oras_bin,
                source=self.source_ref,
                destination=f"{src_layout}:image",
                to_oci_layout=True,
            ).run(dry_run=dry_run)

            # 2. convert local layout -> local layout (directory so we can read
            #    the resulting index.json for its digest).
            self._build_convert(
                "default",
                source=str(src_layout),
                destination=str(out_layout),
                output_format="oci-dir",
            ).run(dry_run=dry_run)

            # 3. push converted layout -> registry, referenced by digest since
            #    the converted layout carries no tag.
            digest = "sha256:<dry-run>" if dry_run else self._read_converted_digest(out_layout)
            OrasCopy(
                oras_bin=self.oras_bin,
                source=f"{out_layout}@{digest}",
                destination=self.destination_ref,
                from_oci_layout=True,
            ).run(dry_run=dry_run)
        except BakeryToolRuntimeError as e:
            return SociConvertWorkflowResult(
                success=False,
                destination_ref=self.destination_ref,
                resolved_namespace=None,
                error=e.dump_stderr() or str(e),
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

        return SociConvertWorkflowResult(
            success=True,
            destination_ref=self.destination_ref,
            resolved_namespace=None,
        )

    def _build_push(self, namespace: str) -> SociPush:
        return SociPush(
            soci_bin=self.soci_bin,
            containerd_namespace=namespace,
            image_ref=self.destination_ref,
            platforms=self.options.platforms,
            sudo=self.sudo,
        )

    def run(self, dry_run: bool = False) -> SociConvertWorkflowResult:
        """Materialize source (if non-standalone), convert, and push."""
        if self.standalone:
            return self._run_standalone(dry_run=dry_run)

        ns = "default"
        try:
            ContainerdImagePull(
                ctr_bin=self.ctr_bin,
                containerd_namespace=ns,
                image_ref=self.source_ref,
                all_platforms=True,
                sudo=self.sudo,
            ).run(dry_run=dry_run)
        except BakeryToolRuntimeError as e:
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
