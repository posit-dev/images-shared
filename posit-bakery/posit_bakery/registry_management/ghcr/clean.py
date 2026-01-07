import logging
import re
from datetime import timedelta

from github import GithubException

from posit_bakery.log import stdout_console
from posit_bakery.registry_management.ghcr.api import GHCRClient
from posit_bakery.registry_management.ghcr.models import GHCRPackageVersions

log = logging.getLogger(__name__)
REGISTRY_PATTERN = re.compile(r"ghcr\.io/(?P<organization>[A-Za-z0-9_.-]+)/(?P<package>[A-Za-z0-9_./-]+)")


def clean_temporary_artifacts(
    ghcr_registry: str,
    remove_untagged: bool = True,
    remove_older_than: timedelta | None = None,
    dry_run: bool = False,
) -> list[GithubException]:
    """Cleans up temporary caches and images that are not tagged or are older than a given timedelta."""
    # Check that the registry matches the expected pattern.
    match = REGISTRY_PATTERN.match(ghcr_registry)
    if not match:
        raise ValueError(f"Invalid GHCR registry format: {ghcr_registry}")
    organization = match.group("organization")
    package = match.group("package")

    log.info(f"Analyzing artifacts in {ghcr_registry}")

    # Retrieve all package versions.
    client = GHCRClient(organization)
    try:
        package_versions = client.get_package_versions(organization, package)
    except GithubException as e:
        log.error(f"Failed to retrieve package versions for {ghcr_registry}: {e}")
        return [e]

    # Filter package versions that should be deleted.
    versions_to_delete = []
    if remove_older_than is not None:
        old_versions = package_versions.older_than(remove_older_than)
        versions_to_delete.extend(old_versions.versions)
    if remove_untagged:
        untagged_versions = package_versions.untagged()
        versions_to_delete.extend(untagged_versions.versions)
    versions_to_delete = list(set(versions_to_delete))  # Deduplicate versions.

    # Process deletions.
    if len(versions_to_delete) > 0:
        log.info(f"Removing {len(versions_to_delete)} artifact(s) from {ghcr_registry}")
        versions_to_delete = GHCRPackageVersions(versions=versions_to_delete)

        if dry_run:
            stdout_console.print_json(versions_to_delete.model_dump_json(indent=2))
        else:
            return client.delete_package_versions(versions_to_delete)
    else:
        log.info(f"No artifacts to remove from {ghcr_registry}")

    return []


def clean_registry(
    image_registry: str,
    remove_tagged_older_than: timedelta | None = timedelta(weeks=80),
    remove_untagged_older_than: timedelta | None = timedelta(weeks=26),
    dry_run: bool = False,
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
    try:
        package_versions = client.get_package_versions(organization, package)
    except GithubException as e:
        log.error(f"Failed to retrieve package versions for {image_registry}: {e}")
        return [e]

    # Filter package versions that should be deleted.
    versions_to_delete = []
    if remove_tagged_older_than is not None:
        old_versions = package_versions.older_than(remove_tagged_older_than)
        versions_to_delete.extend(old_versions.versions)
    if remove_untagged_older_than is not None:
        untagged_versions = package_versions.untagged()
        untagged_old_versions = untagged_versions.older_than(remove_untagged_older_than)
        versions_to_delete.extend(untagged_old_versions.versions)
    versions_to_delete = list(set(versions_to_delete))  # Deduplicate versions.

    # Process deletions.
    if len(versions_to_delete) > 0:
        log.info(f"Removing {len(versions_to_delete)} version(s) from {image_registry}")
        versions_to_delete = GHCRPackageVersions(versions=versions_to_delete)

        if dry_run:
            stdout_console.print_json(versions_to_delete.model_dump_json(indent=2))
        else:
            return client.delete_package_versions(versions_to_delete)
    else:
        log.info(f"No versions to remove from {image_registry}")

    return []
