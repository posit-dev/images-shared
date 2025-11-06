import logging
import re
from datetime import timedelta

from posit_bakery.config import Registry
from posit_bakery.registry_management.ghcr.api import GHCRClient
from posit_bakery.registry_management.ghcr.models import GHCRPackageVersions

log = logging.getLogger(__name__)
REGISTRY_PATTERN = re.compile(r"ghcr\.io/(?P<organization>[A-Za-z0-9_.-]+)/(?P<package>[A-Za-z0-9_./-]+)")


def clean_cache(
    cache_registry: str,
    remove_untagged: bool = True,
    remove_older_than: timedelta | None = timedelta(weeks=2),
):
    """Cleans up dangling caches that have not been updated within 2 weeks or are untagged."""
    # Check that the registry matches the expected pattern.
    match = REGISTRY_PATTERN.match(cache_registry)
    if not match:
        raise ValueError(f"Invalid GHCR registry format: {cache_registry}")
    organization = match.group("organization")
    package = match.group("package")

    # Retrieve all package versions.
    client = GHCRClient(organization)
    package_versions = client.get_package_versions(organization, package)

    # Filter package versions that should be deleted.
    versions_to_delete = []
    if remove_older_than is not None:
        old_versions = package_versions.filter_older_than(remove_older_than)
        versions_to_delete.extend(old_versions.versions)
    if remove_untagged:
        untagged_versions = package_versions.filter_untagged()
        versions_to_delete.extend(untagged_versions.versions)

    # Process deletions.
    if len(versions_to_delete) > 0:
        log.info(f"Removing {len(versions_to_delete)} version(s) from {cache_registry} cache")
        versions_to_delete = GHCRPackageVersions(versions=versions_to_delete)

        client.delete_package_versions(versions_to_delete)
    else:
        log.info(f"No versions to remove from {cache_registry} cache")


def clean_registry(
    image_registry: str,
    remove_tagged_older_than: timedelta | None = timedelta(weeks=80),
    remove_untagged_older_than: timedelta | None = timedelta(weeks=26),
):
    """Cleans up images in the specified registry."""
    # Check that the registry matches the expected pattern.
    match = REGISTRY_PATTERN.match(image_registry)
    if not match:
        raise ValueError(f"Invalid GHCR registry format: {image_registry}")
    organization = match.group("organization")
    package = match.group("package")

    # Retrieve all package versions.
    client = GHCRClient(organization)
    package_versions = client.get_package_versions(organization, package)

    # Filter package versions that should be deleted.
    versions_to_delete = []
    if remove_tagged_older_than is not None:
        old_versions = package_versions.filter_older_than(remove_tagged_older_than)
        versions_to_delete.extend(old_versions.versions)
    if remove_untagged_older_than is not None:
        untagged_versions = package_versions.filter_untagged()
        untagged_old_versions = untagged_versions.filter_older_than(remove_untagged_older_than)
        versions_to_delete.extend(untagged_old_versions.versions)

    # Process deletions.
    if len(versions_to_delete) > 0:
        log.info(f"Removing {len(versions_to_delete)} version(s) from {image_registry}")
        versions_to_delete = GHCRPackageVersions(versions=versions_to_delete)

        client.delete_package_versions(versions_to_delete)
    else:
        log.info(f"No versions to remove from {image_registry}")
