"""Base classes for registry cleanup operations.

This module provides abstract base classes for registry cleanup operations,
enabling consistent cleanup behavior across different registry providers.
"""

import abc
import logging
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Generic, TypeVar

log = logging.getLogger(__name__)

# Type variable for registry-specific version/tag types
VersionT = TypeVar("VersionT")


@dataclass
class RegistryInfo:
    """Parsed registry URL information."""

    organization: str  # namespace for DockerHub
    package: str  # repository for DockerHub
    raw_url: str


class BaseRegistryCleaner(abc.ABC, Generic[VersionT]):
    """Abstract base class for registry cleanup operations.

    Provides a template method pattern for cleaning registry artifacts.
    Subclasses implement registry-specific operations while sharing
    common cleanup logic.

    Type parameter VersionT represents the registry-specific version/tag type.
    """

    # Subclasses must define their registry URL pattern
    REGISTRY_PATTERN: re.Pattern[str]
    REGISTRY_NAME: str  # e.g., "GHCR", "Docker Hub"

    def parse_registry_url(self, registry_url: str) -> RegistryInfo:
        """Parse and validate a registry URL.

        :param registry_url: Full registry URL to parse.
        :return: RegistryInfo with parsed components.
        :raises ValueError: If URL doesn't match expected pattern.
        """
        match = self.REGISTRY_PATTERN.match(registry_url)
        if not match:
            raise ValueError(f"Invalid {self.REGISTRY_NAME} registry format: {registry_url}")

        groups = match.groupdict()
        return RegistryInfo(
            organization=groups.get("organization") or groups.get("namespace", ""),
            package=groups.get("package") or groups.get("repository", ""),
            raw_url=registry_url,
        )

    @abc.abstractmethod
    def get_client(self, registry_info: RegistryInfo) -> Any:
        """Create a client for the registry.

        :param registry_info: Parsed registry information.
        :return: Registry-specific client instance.
        """
        pass

    @abc.abstractmethod
    def get_versions(self, client: Any, registry_info: RegistryInfo) -> list[VersionT]:
        """Retrieve all versions/tags from the registry.

        :param client: Registry client instance.
        :param registry_info: Parsed registry information.
        :return: List of version/tag objects.
        """
        pass

    @abc.abstractmethod
    def filter_versions(
        self,
        versions: list[VersionT],
        remove_tagged_older_than: timedelta | None,
        remove_untagged_older_than: timedelta | None,
    ) -> list[VersionT]:
        """Filter versions based on age and tag status.

        :param versions: All versions from registry.
        :param remove_tagged_older_than: Remove tagged versions older than this.
        :param remove_untagged_older_than: Remove untagged versions older than this.
        :return: List of versions to delete.
        """
        pass

    @abc.abstractmethod
    def delete_versions(self, client: Any, versions: list[VersionT]) -> list[Exception]:
        """Delete the specified versions.

        :param client: Registry client instance.
        :param versions: Versions to delete.
        :return: List of exceptions encountered during deletion.
        """
        pass

    @abc.abstractmethod
    def report_versions(self, versions: list[VersionT]) -> None:
        """Report versions that would be deleted (for dry run).

        :param versions: Versions that would be deleted.
        """
        pass

    def clean_registry(
        self,
        image_registry: str,
        remove_tagged_older_than: timedelta | None = timedelta(weeks=80),
        remove_untagged_older_than: timedelta | None = timedelta(weeks=26),
        dry_run: bool = False,
    ) -> list[Exception]:
        """Clean up images in the specified registry.

        Template method that orchestrates the cleanup process.

        :param image_registry: Registry URL to clean.
        :param remove_tagged_older_than: Remove tagged versions older than this.
        :param remove_untagged_older_than: Remove untagged versions older than this.
        :param dry_run: If True, only report what would be deleted.
        :return: List of exceptions encountered during cleanup.
        """
        registry_info = self.parse_registry_url(image_registry)

        client = self.get_client(registry_info)
        try:
            versions = self.get_versions(client, registry_info)
        except Exception as e:
            log.error(f"Failed to retrieve versions for {image_registry}: {e}")
            return [e]

        versions_to_delete = self.filter_versions(versions, remove_tagged_older_than, remove_untagged_older_than)
        versions_to_delete = list(set(versions_to_delete))  # Deduplicate

        if not versions_to_delete:
            log.info(f"No versions to remove from {image_registry}")
            return []

        log.info(f"Removing {len(versions_to_delete)} version(s) from {image_registry}")

        if dry_run:
            self.report_versions(versions_to_delete)
            return []

        return self.delete_versions(client, versions_to_delete)
