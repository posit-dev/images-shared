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

    @property
    def command(self) -> list[str]:
        """Build the oras cp command."""
        cmd = [self.oras_bin, "cp"]
        if self.plain_http:
            cmd.append("--plain-http")
        cmd.extend([self.source, self.destination])
        return cmd


class OrasManifestDelete(OrasCommand):
    """Delete a manifest from a registry.

    This command deletes a manifest (image or index) from a registry.
    """

    reference: Annotated[str, Field(description="The manifest reference to delete.")]

    @property
    def command(self) -> list[str]:
        """Build the oras manifest delete command."""
        cmd = [self.oras_bin, "manifest", "delete", "--force"]
        if self.plain_http:
            cmd.append("--plain-http")
        cmd.append(self.reference)
        return cmd


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
    3. Deletes the temporary index
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
        """Run the merge workflow.

        :param dry_run: If True, log commands without executing them.
        :return: Result of the workflow execution.
        """

        log.info(f"Starting ORAS merge workflow for {self.image_target.image_name}")
        log.debug(f"Sources: {self.sources}")
        log.debug(f"Temporary index: {self.temp_index_tag}")
        log.debug(f"Destinations: {', '.join(self.image_target.tags.as_strings())}")

        try:
            # Step 1: Create the manifest index
            log.info(f"Creating manifest index at {self.temp_index_tag}")
            create_cmd = OrasManifestIndexCreate(
                oras_bin=self.oras_bin,
                sources=self.image_target.get_merge_sources(),
                destination=self.temp_index_tag,
                annotations=self.annotations,
                plain_http=self.plain_http,
            )
            create_cmd.run(dry_run=dry_run)

            # Step 2: Copy to all destinations
            for destination, tags in itertools.groupby(self.image_target.tags, lambda x: x.destination):
                log.info(f"Copying index to {destination}")
                combine_tag_str = destination + ":" + ",".join(tag.suffix for tag in tags)
                copy_cmd = OrasCopy(
                    oras_bin=self.oras_bin,
                    source=self.temp_index_tag,
                    destination=combine_tag_str,
                    plain_http=self.plain_http,
                )
                copy_cmd.run(dry_run=dry_run)

            # Step 3: Delete the temporary index
            log.info(f"Cleaning up temporary index {self.temp_index_tag}")
            delete_cmd = OrasManifestDelete(
                oras_bin=self.oras_bin,
                reference=self.temp_index_tag,
                plain_http=self.plain_http,
            )
            delete_cmd.run(dry_run=dry_run)

            log.info(f"ORAS merge workflow completed successfully")
            return OrasMergeWorkflowResult(
                success=True,
                temp_index_ref=self.temp_index_tag,
                destinations=self.image_target.tags.as_strings(),
            )

        except BakeryToolRuntimeError as e:
            log.error(f"ORAS merge workflow failed: {e}")
            return OrasMergeWorkflowResult(
                success=False,
                temp_index_ref=self.temp_index_tag,
                destinations=self.image_target.tags.as_strings(),
                error=str(e),
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
