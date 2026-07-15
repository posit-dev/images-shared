"""SOCI CLI integration module."""

import json
import logging
import shutil
import subprocess
import tempfile
from abc import ABC, abstractmethod
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.imagetools.oras import OrasCopy
from posit_bakery.plugins.builtin.imagetools.options import SociOptions
from posit_bakery.retry import RetryPolicy, retry_on_transient
from posit_bakery.util import find_bin

if TYPE_CHECKING:
    from posit_bakery.parallel import CommandRunner

log = logging.getLogger(__name__)


@cache
def find_soci_bin(context: Path) -> str:
    """Resolve a path or PATH-resident name for the soci binary.

    Memoized so a publish run with multiple SOCI-enabled targets resolves the
    binary once, rather than once per target.

    :param context: Project context to search for the binary in.
    :return: Path to the soci binary, or the bare name "soci" when it
        resolves through PATH.
    :raises BakeryToolNotFoundError: If soci cannot be found.
    """
    return find_bin(context, "soci", "SOCI_PATH") or "soci"


class SociCommand(BaseModel, ABC):
    """Base class for soci CLI invocations."""

    soci_bin: Annotated[str, Field(description="Path to the soci binary.")]

    @property
    @abstractmethod
    def command(self) -> list[str]:
        """Return the full command to execute."""
        ...

    def run(self, dry_run: bool = False, runner: "CommandRunner | None" = None) -> subprocess.CompletedProcess:
        """Execute the soci command.

        :param dry_run: If True, log the command without executing it.
        :param runner: When provided, spawn through this tracked :class:`CommandRunner`
            instead of calling ``subprocess.run()`` directly. See ``OrasCommand.run()`` for
            why this exists.
        :return: The completed process result.
        :raises BakeryToolRuntimeError: On non-zero exit.
        """
        cmd = self.command
        log.debug(f"Executing soci command: {' '.join(cmd)}")

        if dry_run:
            log.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        result = runner.run(cmd) if runner is not None else subprocess.run(cmd, capture_output=True)

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
    """`soci convert --standalone` wrapper.

    Standalone (file-to-file) conversion: source and destination are
    filesystem paths to OCI layouts (archive or directory). containerd is
    never involved.
    """

    source: Annotated[str, Field(description="Source OCI-layout path.")]
    destination: Annotated[str, Field(description="Destination OCI-layout path.")]
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
        Field(default="oci-archive", description="Standalone-mode output layout."),
    ]

    @property
    def command(self) -> list[str]:
        cmd: list[str] = [self.soci_bin, "convert", "--standalone", "--format", self.output_format]
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


class SociConvertWorkflowResult(BaseModel):
    success: Annotated[bool, Field(description="Whether the workflow completed successfully.")]
    destination_ref: Annotated[str | None, Field(default=None, description="SOCI-enabled destination ref.")]
    error: Annotated[str | None, Field(default=None, description="Error message if the workflow failed.")]


class SociConvertWorkflow(BaseModel):
    """Pull a source ref into an OCI layout, convert it to SOCI, and push it
    back to the registry — all without containerd (standalone mode)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    soci_bin: Annotated[str, Field(description="Path to the soci binary.")]
    oras_bin: Annotated[str, Field(description="Path to the oras binary.")]
    image_target: Annotated[ImageTarget, Field(description="The image target.")]
    options: Annotated[SociOptions, Field(description="Per-target SOCI configuration.")]
    source_ref: Annotated[str, Field(description="Temp-registry ref to convert from.")]
    retry_policy: Annotated[RetryPolicy, Field(default_factory=RetryPolicy)]

    @property
    def destination_ref(self) -> str:
        """SOCI-enabled destination ref. The on-disk OCI layouts are internal
        scratch; the converted image is pushed here at the end via oras."""
        return f"{self.source_ref}-soci"

    def _build_convert(
        self,
        *,
        source: str,
        destination: str,
        output_format: Literal["oci-archive", "oci-dir"] = "oci-dir",
    ) -> SociConvert:
        return SociConvert(
            soci_bin=self.soci_bin,
            source=source,
            destination=destination,
            platforms=self.options.platforms,
            span_size=self.options.span_size,
            min_layer_size=self.options.min_layer_size,
            prefetch_files=self.options.prefetch_files,
            optimizations=self.options.optimizations,
            output_format=output_format,
        )

    @staticmethod
    def _read_converted_digest(layout: Path) -> str:
        """Return the digest of the top-level manifest in a converted OCI
        layout. soci writes the converted image to ``index.json`` without a
        tag, so the only way to reference it for the push back is by digest."""
        index = json.loads((layout / "index.json").read_text())
        return index["manifests"][0]["digest"]

    def run(self, dry_run: bool = False, runner: "CommandRunner | None" = None) -> SociConvertWorkflowResult:
        """Pull the source ref into an OCI layout, convert it to SOCI with
        ``soci convert --standalone``, and push the converted layout back to
        the registry.

        oras bridges the registry on both ends: ``--to-oci-layout`` to
        materialize the source as an OCI layout, ``--from-oci-layout`` to push
        the converted result. The scratch layouts are removed afterward.
        """
        log.info(f"Running SOCI conversion on {self.image_target.uid}")
        scratch = Path(tempfile.mkdtemp(prefix="soci-standalone-"))
        src_layout = scratch / "src"
        out_layout = scratch / "out"
        try:
            # 1. registry -> OCI layout. The layout tag is arbitrary; soci
            #    reads the whole layout. Retry transient registry errors: the
            #    temp-registry index/children may still be propagating when
            #    this pull first reads them (registry eventual consistency).
            pull = OrasCopy(
                oras_bin=self.oras_bin,
                source=self.source_ref,
                destination=f"{src_layout}:image",
                to_oci_layout=True,
            )
            retry_on_transient(
                lambda: pull.run(dry_run=dry_run, runner=runner),
                policy=self.retry_policy,
                description=f"soci pull for '{self.image_target.uid}'",
            )

            # 2. convert local layout -> local layout (directory so we can read
            #    the resulting index.json for its digest).
            self._build_convert(
                source=str(src_layout),
                destination=str(out_layout),
                output_format="oci-dir",
            ).run(dry_run=dry_run, runner=runner)

            # 3. push converted layout -> registry, referenced by digest since
            #    the converted layout carries no tag.
            digest = "sha256:<dry-run>" if dry_run else self._read_converted_digest(out_layout)
            OrasCopy(
                oras_bin=self.oras_bin,
                source=f"{out_layout}@{digest}",
                destination=self.destination_ref,
                from_oci_layout=True,
            ).run(dry_run=dry_run, runner=runner)
        except BakeryToolRuntimeError as e:
            return SociConvertWorkflowResult(
                success=False,
                destination_ref=self.destination_ref,
                error=e.dump_stderr() or str(e),
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

        return SociConvertWorkflowResult(
            success=True,
            destination_ref=self.destination_ref,
        )
