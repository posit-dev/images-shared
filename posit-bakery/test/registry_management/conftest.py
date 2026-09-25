"""Shared fixtures for registry_management tests."""

import json
from pathlib import Path

import pytest

from posit_bakery.registry_management.ghcr.models import GHCRPackageVersions

# Re-use the test data from config tests since the data format is the same
CONFIG_TESTDATA_DIR = Path(__file__).parent.parent / "config" / "testdata"
CACHE_GHCR_PACKAGE_VERSIONS = CONFIG_TESTDATA_DIR / "cache_ghcr_package_versions.json"
TEMP_GHCR_PACKAGE_VERSIONS = CONFIG_TESTDATA_DIR / "temp_ghcr_package_versions.json"


@pytest.fixture()
def cache_ghcr_package_versions_data():
    """Return the GHCR package versions test data for cache registries."""
    return GHCRPackageVersions(versions=json.loads(CACHE_GHCR_PACKAGE_VERSIONS.read_text()))


@pytest.fixture()
def temp_ghcr_package_versions_data():
    """Return the GHCR package versions test data for temp registries."""
    return GHCRPackageVersions(versions=json.loads(TEMP_GHCR_PACKAGE_VERSIONS.read_text()))
