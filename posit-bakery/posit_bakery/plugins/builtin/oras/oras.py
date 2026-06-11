import hashlib
import itertools
import logging
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.image.image_target import ImageTarget, Tag
from posit_bakery.util import find_bin

log = logging.getLogger(__name__)


def find_oras_bin(context: Path) -> str:
    """Find the path to the oras binary.

    :param context: The project context to search for the binary in.
    :return: The path to the oras binary.
    :raises BakeryToolNotFoundError: If the oras binary cannot be found.
    """
    return find_bin(context, "oras", "ORAS_PATH") or "oras"


def get_repository_from_ref(ref: str) -> str:
    """Extract the full repository (registry/repo) from an image reference.

    :param ref: The image reference.
    :return: The registry and repository portion (without tag or digest).
    """
    tag = Tag.from_string(ref)
    return tag.destination


class OrasCommand(BaseModel, ABC):
    """Base class for oras CLI commands."""

    oras_bin: Annotated[str, Field(description="Path to the oras binary.")]
    plain_http: Annotated[bool, Field(default=False, description="Use plain HTTP for registry connections.")]

    @property
    @abstractmethod
    def command(self) -> list[str]:
        """Return the full command to execute."""
        ...

    def run(self, dry_run: bool = False) -> subprocess.CompletedProcess:
        """Execute the oras command.

        :param dry_run: If True, log the command without executing it.
        :return: The completed process result.
        :raises BakeryToolRuntimeError: If the command fails.
        """
        cmd = self.command
        log.debug(f"Executing oras command: {' '.join(cmd)}")

        if dry_run:
            log.info(f"[DRY RUN] Would execute: {' '.join(cmd)}")
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"", stderr=b"")

        result = subprocess.run(cmd, capture_output=True)

        if result.returncode != 0:
            raise BakeryToolRuntimeError(
                message=f"oras command failed",
                tool_name="oras",
                cmd=cmd,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
            )

        return result


class OrasManifestIndexCreate(OrasCommand):
    """Create a manifest index from multiple source images.

    This command creates a multi-platform manifest index pointing to the provided
    source images and pushes it to the destination reference.
    """

    sources: Annotated[list[str], Field(description="List of source image references to include in the index.")]
    destination: Annotated[str, Field(description="Destination reference for the created index.")]
    annotations: Annotated[dict[str, str], Field(default_factory=dict, description="Annotations to add to the index.")]

    @model_validator(mode="after")
    def validate_sources_same_repository(self) -> Self:
        """Validate that all sources are from the same repository.

        oras manifest index create requires all sources to be in the same repository
        because it creates an index that references existing manifests by digest.
        """
        if not self.sources:
            raise ValueError("At least one source is required.")

        repositories = set()
        for source in self.sources:
            repo = get_repository_from_ref(source)
            repositories.add(repo)

        if len(repositories) > 1:
            raise ValueError(f"All sources must be from the same repository. Found: {', '.join(sorted(repositories))}")

        return self

    @property
    def command(self) -> list[str]:
        """Build the oras manifest index create command."""
        cmd = [self.oras_bin, "manifest", "index", "create"]
        if self.plain_http:
            cmd.append("--plain-http")
        cmd.append(self.destination)
        cmd.extend(self.sources)

        for key, value in self.annotations.items():
            cmd.extend(["--annotation", f"{key}={value}"])

        return cmd


class OrasCopy(OrasCommand):
    """Copy an image from source to destination.

    This command copies an image (including manifest indexes) from one location
    to another, supporting cross-registry copies.
    """

    source: Annotated[str, Field(description="Source image reference to copy.")]
    destination: Annotated[str, Field(description="Destination reference.")]
    from_oci_layout: Annotated[
        bool,
        Field(default=False, description="Treat the source as an OCI image layout (tar or directory) path."),
    ]
    to_oci_layout: Annotated[
        bool,
        Field(default=False, description="Treat the destination as an OCI image layout (tar or directory) path."),
    ]

    @property
    def command(self) -> list[str]:
        """Build the oras cp command."""
        cmd = [self.oras_bin, "cp"]
        if self.plain_http:
            cmd.append("--plain-http")
        if self.from_oci_layout:
            cmd.append("--from-oci-layout")
        if self.to_oci_layout:
            cmd.append("--to-oci-layout")
        cmd.extend([self.source, self.destination])
        return cmd


class OrasManifestFetch(OrasCommand):
    """Fetch a manifest (or its descriptor) to verify a reference exists.

    Used as a post-copy existence check on final destination tags. ``oras
    manifest fetch`` resolves the reference against the registry and exits
    non-zero (raising :class:`BakeryToolRuntimeError`) if the tag is missing.
    """

    reference: Annotated[str, Field(description="Image reference whose manifest to fetch.")]
    descriptor: Annotated[
        bool,
        Field(
            default=False,
            description="Fetch only the manifest descriptor instead of the full manifest body (lighter existence check).",
        ),
    ]

    @property
    def command(self) -> list[str]:
        """Build the oras manifest fetch command."""
        cmd = [self.oras_bin, "manifest", "fetch"]
        if self.plain_http:
            cmd.append("--plain-http")
        if self.descriptor:
            cmd.append("--descriptor")
        cmd.append(self.reference)
        return cmd


class OrasIndexCreateResult(BaseModel):
    """Result of an ORAS manifest-index-create phase."""

    success: Annotated[bool, Field(description="Whether the create phase succeeded.")]
    temp_ref: Annotated[str, Field(description="The temp ref of the created index.")]
    error: Annotated[str | None, Field(default=None, description="Error message on failure.")]


class OrasIndexCreateWorkflow(BaseModel):
    """Create the multi-platform manifest index at the temp registry."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    oras_bin: Annotated[str, Field(description="Path to the oras binary.")]
    image_target: Annotated[ImageTarget, Field(description="Target this index represents.")]
    annotations: Annotated[dict[str, str], Field(default_factory=dict)]
    plain_http: Annotated[bool, Field(default=False)]

    @property
    def temp_index_tag(self) -> str:
        source_hash = hashlib.sha256("".join(self.image_target.get_merge_sources()).encode("UTF-8")).hexdigest()[:10]
        return (
            f"{self.image_target.temp_registry}/{self.image_target.image_name}/tmp:{self.image_target.uid}{source_hash}"
        )

    def run(self, dry_run: bool = False) -> OrasIndexCreateResult:
        try:
            OrasManifestIndexCreate(
                oras_bin=self.oras_bin,
                sources=self.image_target.get_merge_sources(),
                destination=self.temp_index_tag,
                annotations=self.annotations,
                plain_http=self.plain_http,
            ).run(dry_run=dry_run)
            return OrasIndexCreateResult(success=True, temp_ref=self.temp_index_tag)
        except BakeryToolRuntimeError as e:
            log.error(f"oras index-create failed: {e}")
            return OrasIndexCreateResult(success=False, temp_ref=self.temp_index_tag, error=str(e))


class OrasIndexCopyResult(BaseModel):
    """Result of an ORAS index-copy phase."""

    success: Annotated[bool, Field(description="Whether all copies succeeded.")]
    destinations: Annotated[list[str], Field(default_factory=list)]
    error: Annotated[str | None, Field(default=None)]


class OrasIndexCopyWorkflow(BaseModel):
    """Copy a temp-registry ref to each configured destination."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    oras_bin: Annotated[str, Field(description="Path to the oras binary.")]
    image_target: Annotated[ImageTarget, Field(description="Target whose tags to fan out to.")]
    plain_http: Annotated[bool, Field(default=False)]

    def run(self, source: str, dry_run: bool = False) -> OrasIndexCopyResult:
        try:
            destinations = []
            for destination, tags in itertools.groupby(self.image_target.tags, lambda x: x.destination):
                combined = destination + ":" + ",".join(t.suffix for t in tags)
                OrasCopy(
                    oras_bin=self.oras_bin,
                    source=source,
                    destination=combined,
                    plain_http=self.plain_http,
                ).run(dry_run=dry_run)
                destinations.append(combined)
            return OrasIndexCopyResult(success=True, destinations=destinations)
        except BakeryToolRuntimeError as e:
            log.error(f"oras index-copy failed: {e}")
            return OrasIndexCopyResult(
                success=False,
                destinations=self.image_target.tags.as_strings(),
                error=str(e),
            )


class OrasIndexVerifyResult(BaseModel):
    """Result of an ORAS index-verify phase."""

    success: Annotated[bool, Field(description="Whether every destination tag was verified.")]
    verified: Annotated[
        list[str], Field(default_factory=list, description="Destination refs successfully verified, in order.")
    ]
    error: Annotated[str | None, Field(default=None, description="Error message on the first failed verification.")]


class OrasIndexVerifyWorkflow(BaseModel):
    """Verify that each final destination tag exists in its registry.

    Run after :class:`OrasIndexCopyWorkflow` as a sanity check that the copied
    indexes are actually resolvable. Each tag is fetched with ``oras manifest
    fetch --descriptor``; the first missing tag aborts the workflow.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    oras_bin: Annotated[str, Field(description="Path to the oras binary.")]
    image_target: Annotated[ImageTarget, Field(description="Target whose destination tags to verify.")]
    plain_http: Annotated[bool, Field(default=False)]

    def run(self, dry_run: bool = False) -> OrasIndexVerifyResult:
        verified: list[str] = []
        try:
            for ref in self.image_target.tags.as_strings():
                OrasManifestFetch(
                    oras_bin=self.oras_bin,
                    reference=ref,
                    descriptor=True,
                    plain_http=self.plain_http,
                ).run(dry_run=dry_run)
                verified.append(ref)
            return OrasIndexVerifyResult(success=True, verified=verified)
        except BakeryToolRuntimeError as e:
            log.error(f"oras manifest verify failed: {e}")
            return OrasIndexVerifyResult(success=False, verified=verified, error=str(e))


class OrasMergeWorkflowResult(BaseModel):
    """Result of an ORAS merge workflow execution."""

    success: Annotated[bool, Field(description="Whether the workflow completed successfully.")]
    temp_index_ref: Annotated[str | None, Field(default=None, description="Reference to the temporary index created.")]
    destinations: Annotated[list[str], Field(default_factory=list, description="List of destination references.")]
    error: Annotated[str | None, Field(default=None, description="Error message if the workflow failed.")]


class OrasMergeWorkflow(BaseModel):
    """Orchestrates the multi-platform merge workflow using oras.

    This workflow:
    1. Creates a temporary manifest index from platform-specific source images
    2. Copies the index to all target registries/tags

    The temporary index is left in place and is cleaned up out-of-band by the
    ``clean.yml`` workflow (``bakery clean temp-registry``) rather than deleted here.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    oras_bin: Annotated[str, Field(description="Path to the oras binary.")]
    image_target: Annotated[ImageTarget, Field(description="The image target of the sources.")]
    annotations: Annotated[dict[str, str], Field(default_factory=dict, description="Annotations for the index.")]
    plain_http: Annotated[bool, Field(default=False, description="Use plain HTTP for registry connections.")]

    @model_validator(mode="after")
    def validate_sources(self) -> Self:
        """Validate that sources are provided."""
        if not self.image_target.get_merge_sources():
            raise ValueError("At least one source is required.")
        return self

    @property
    def sources(self) -> list[str]:
        """Get the list of source image references from the image target."""
        return self.image_target.get_merge_sources()

    @property
    def temp_index_tag(self) -> str:
        """Generate a unique temporary index tag."""
        source_hash = hashlib.sha256("".join(self.image_target.get_merge_sources()).encode("UTF-8")).hexdigest()[:10]
        return (
            f"{self.image_target.temp_registry}/{self.image_target.image_name}/tmp:{self.image_target.uid}{source_hash}"
        )

    def run(self, dry_run: bool = False) -> OrasMergeWorkflowResult:
        """Compose create → copy. Preserved as a single call for back-compat
        with the `bakery oras merge` CLI.

        The temporary index is intentionally left in place; it is cleaned up
        out-of-band by the ``clean.yml`` workflow (``bakery clean temp-registry``)
        rather than deleted here.
        """
        log.info(f"Starting ORAS merge workflow for {self.image_target.image_name}")
        create = OrasIndexCreateWorkflow(
            oras_bin=self.oras_bin,
            image_target=self.image_target,
            annotations=self.annotations,
            plain_http=self.plain_http,
        ).run(dry_run=dry_run)
        if not create.success:
            return OrasMergeWorkflowResult(
                success=False,
                temp_index_ref=create.temp_ref,
                destinations=self.image_target.tags.as_strings(),
                error=create.error,
            )

        copy = OrasIndexCopyWorkflow(
            oras_bin=self.oras_bin,
            image_target=self.image_target,
            plain_http=self.plain_http,
        ).run(source=create.temp_ref, dry_run=dry_run)

        return OrasMergeWorkflowResult(
            success=copy.success,
            temp_index_ref=create.temp_ref,
            destinations=self.image_target.tags.as_strings(),
            error=copy.error,
        )

    @classmethod
    def from_image_target(
        cls, target: "ImageTarget", oras_bin: str | None = None, plain_http: bool = False
    ) -> "OrasMergeWorkflow":
        """Create an OrasMergeWorkflow from an ImageTarget.

        :param target: The ImageTarget to merge.
        :param oras_bin: Path to the oras binary. If not provided, will be discovered.
        :param plain_http: Use plain HTTP for registry connections (useful for local registries).
        :return: A configured OrasMergeWorkflow instance.
        :raises ValueError: If the target is missing required settings.
        """
        # Import here to avoid circular imports

        if not target.settings.temp_registry:
            raise ValueError("ImageTarget must have temp_registry set in settings for ORAS merge workflow.")

        if oras_bin is None:
            oras_bin = find_oras_bin(target.context.base_path)

        return cls(
            oras_bin=oras_bin,
            image_target=target,
            annotations=target.labels,
            plain_http=plain_http,
        )
