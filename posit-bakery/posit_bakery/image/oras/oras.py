"""ORAS CLI integration for multi-platform manifest management.

This module provides an alternative to `docker buildx imagetools create` for merging
multi-platform images. It uses the oras CLI to create manifest indexes and copy them
to target registries, avoiding authentication issues that affect Docker's imagetools
when performing cross-registry operations.
"""

import logging
import subprocess
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Annotated, Self
from urllib.parse import urlparse

from pydantic import BaseModel, Field, model_validator

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.util import find_bin

log = logging.getLogger(__name__)


def find_oras_bin(context: Path) -> str:
    """Find the path to the oras binary.

    :param context: The project context to search for the binary in.
    :return: The path to the oras binary.
    :raises BakeryToolNotFoundError: If the oras binary cannot be found.
    """
    return find_bin(context, "oras", "ORAS_PATH") or "oras"


def parse_image_reference(ref: str) -> tuple[str, str, str]:
    """Parse an image reference into its components.

    :param ref: The image reference to parse (e.g., "registry.io/repo/image@sha256:digest").
    :return: A tuple of (registry, repository, tag_or_digest).
    """
    # Handle digest references
    if "@" in ref:
        name_part, digest = ref.rsplit("@", 1)
        tag_or_digest = f"@{digest}"
    elif ":" in ref and not ref.rsplit(":", 1)[-1].startswith("sha256"):
        # Handle tag references, but be careful with ports
        parts = ref.rsplit(":", 1)
        # Check if the last part looks like a port (all digits)
        if parts[-1].isdigit():
            name_part = ref
            tag_or_digest = ""
        else:
            name_part = parts[0]
            tag_or_digest = f":{parts[1]}"
    else:
        name_part = ref
        tag_or_digest = ""

    # Split registry from repository
    if "/" in name_part:
        first_part = name_part.split("/")[0]
        # Check if first part looks like a registry (contains . or :)
        if "." in first_part or ":" in first_part:
            registry = first_part
            repository = "/".join(name_part.split("/")[1:])
        else:
            # Default registry
            registry = "docker.io"
            repository = name_part
    else:
        registry = "docker.io"
        repository = name_part

    return registry, repository, tag_or_digest


def get_repository_from_ref(ref: str) -> str:
    """Extract the full repository (registry/repo) from an image reference.

    :param ref: The image reference.
    :return: The registry and repository portion (without tag or digest).
    """
    registry, repository, _ = parse_image_reference(ref)
    return f"{registry}/{repository}"


class OrasCommand(BaseModel, ABC):
    """Base class for oras CLI commands."""

    oras_bin: Annotated[str, Field(description="Path to the oras binary.")]

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
        cmd = [self.oras_bin, "manifest", "index", "create", self.destination]
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
        return [self.oras_bin, "cp", self.source, self.destination]


class OrasManifestDelete(OrasCommand):
    """Delete a manifest from a registry.

    This command deletes a manifest (image or index) from a registry.
    """

    reference: Annotated[str, Field(description="The manifest reference to delete.")]

    @property
    def command(self) -> list[str]:
        """Build the oras manifest delete command."""
        return [self.oras_bin, "manifest", "delete", "--force", self.reference]


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

    oras_bin: Annotated[str, Field(description="Path to the oras binary.")]
    sources: Annotated[list[str], Field(description="List of source image references (one per platform).")]
    temp_registry: Annotated[str, Field(description="Registry to use for temporary index storage.")]
    image_name: Annotated[str, Field(description="Name of the image (used for temp tag).")]
    tag_suffixes: Annotated[list[str], Field(description="Tag suffixes to apply to the final image.")]
    target_registries: Annotated[list[str], Field(description="Target registries to push to.")]
    annotations: Annotated[dict[str, str], Field(default_factory=dict, description="Annotations for the index.")]

    @model_validator(mode="after")
    def validate_sources(self) -> Self:
        """Validate that sources are provided."""
        if not self.sources:
            raise ValueError("At least one source is required.")
        return self

    @property
    def temp_index_tag(self) -> str:
        """Generate a unique temporary index tag."""
        uid = str(uuid.uuid4())[:8]
        return f"{self.temp_registry}/{self.image_name}/tmp:{uid}"

    def _get_destinations(self) -> list[str]:
        """Generate all destination references."""
        destinations = []
        for registry in self.target_registries:
            for suffix in self.tag_suffixes:
                # Check if registry already includes a repository path
                if "/" in registry.split(":", 1)[0].split("/", 1)[-1]:
                    # Registry includes repository (e.g., "ghcr.io/org/repo")
                    destinations.append(f"{registry}:{suffix}")
                else:
                    # Registry is just the host (e.g., "ghcr.io")
                    destinations.append(f"{registry}/{self.image_name}:{suffix}")
        return destinations

    def execute(self, dry_run: bool = False) -> OrasMergeWorkflowResult:
        """Execute the merge workflow.

        :param dry_run: If True, log commands without executing them.
        :return: Result of the workflow execution.
        """
        temp_ref = self.temp_index_tag
        destinations = self._get_destinations()

        log.info(f"Starting ORAS merge workflow for {self.image_name}")
        log.debug(f"Sources: {self.sources}")
        log.debug(f"Temporary index: {temp_ref}")
        log.debug(f"Destinations: {destinations}")

        try:
            # Step 1: Create the manifest index
            log.info(f"Creating manifest index at {temp_ref}")
            create_cmd = OrasManifestIndexCreate(
                oras_bin=self.oras_bin,
                sources=self.sources,
                destination=temp_ref,
                annotations=self.annotations,
            )
            create_cmd.run(dry_run=dry_run)

            # Step 2: Copy to all destinations
            for dest in destinations:
                log.info(f"Copying index to {dest}")
                copy_cmd = OrasCopy(
                    oras_bin=self.oras_bin,
                    source=temp_ref,
                    destination=dest,
                )
                copy_cmd.run(dry_run=dry_run)

            # Step 3: Delete the temporary index
            log.info(f"Cleaning up temporary index {temp_ref}")
            delete_cmd = OrasManifestDelete(
                oras_bin=self.oras_bin,
                reference=temp_ref,
            )
            delete_cmd.run(dry_run=dry_run)

            log.info(f"ORAS merge workflow completed successfully")
            return OrasMergeWorkflowResult(
                success=True,
                temp_index_ref=temp_ref,
                destinations=destinations,
            )

        except BakeryToolRuntimeError as e:
            log.error(f"ORAS merge workflow failed: {e}")
            return OrasMergeWorkflowResult(
                success=False,
                temp_index_ref=temp_ref,
                destinations=destinations,
                error=str(e),
            )

    @classmethod
    def from_image_target(cls, target: "ImageTarget", oras_bin: str | None = None) -> "OrasMergeWorkflow":
        """Create an OrasMergeWorkflow from an ImageTarget.

        :param target: The ImageTarget to merge.
        :param oras_bin: Path to the oras binary. If not provided, will be discovered.
        :return: A configured OrasMergeWorkflow instance.
        :raises ValueError: If the target is missing required settings.
        """
        # Import here to avoid circular imports
        from posit_bakery.image.image_target import ImageTarget

        if not target.settings.temp_registry:
            raise ValueError("ImageTarget must have temp_registry set in settings for ORAS merge workflow.")

        if oras_bin is None:
            oras_bin = find_oras_bin(target.context.base_path)

        sources = target._get_merge_sources()

        # Convert labels to annotations
        annotations = {k: v for k, v in target.labels.items()}

        # Get target registries - extract base URLs from registries
        target_registries = []
        for registry in target.image_version.all_registries:
            if hasattr(registry, "repository"):
                target_registries.append(f"{registry.base_url}/{registry.repository}")
            else:
                target_registries.append(f"{registry.base_url}/{target.image_name}")

        return cls(
            oras_bin=oras_bin,
            sources=sources,
            temp_registry=target.settings.temp_registry,
            image_name=target.image_name,
            tag_suffixes=target.tag_suffixes,
            target_registries=target_registries,
            annotations=annotations,
        )
