import re

from posit_bakery.registry_management.ghcr.api import github_client, get_package_versions, delete_package_versions
from posit_bakery.registry_management.ghcr.models import GHCRPackageVersions

REGISTRY_PATTERN = re.compile(r"ghcr\.io/(?P<organization>[A-Za-z0-9_.-]+)/(?P<package>[A-Za-z0-9_./-]+)")


def clean_cache(cache_registry: str):
    """Cleans up dangling caches that have not been updated within 2 weeks or are untagged."""
    # Check that the registry matches the expected pattern.
    match = REGISTRY_PATTERN.match(cache_registry)
    if not match:
        raise ValueError(f"Invalid GHCR registry format: {cache_registry}")
    organization = match.group("organization")
    package = match.group("package")

    client = github_client()
    package_versions = get_package_versions(client, organization, package)
    old_versions = package_versions.filter_older_than()
    untagged_versions = package_versions.filter_untagged()
    versions_to_delete = GHCRPackageVersions(versions=[*old_versions.versions, *untagged_versions.versions])

    delete_package_versions(client, versions_to_delete)
