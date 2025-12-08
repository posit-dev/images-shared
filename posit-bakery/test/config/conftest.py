import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
import requests

from posit_bakery.config import ImageVariant
import posit_bakery.config.dependencies.const as dependencies_const
import posit_bakery.config.image.posit_product.const as product_const
from posit_bakery.registry_management.ghcr.models import GHCRPackageVersions

CONFIG_TESTDATA_DIR = Path(os.path.dirname(__file__)) / "testdata"
GHCR_PACKAGE_VERSIONS = CONFIG_TESTDATA_DIR / "ghcr_package_versions.json"


DEPENDENCIES_TESTDATA_DIR = Path(os.path.dirname(__file__)) / "dependencies" / "testdata"
PYTHON_STANDALONE = DEPENDENCIES_TESTDATA_DIR / "download-metadata.json"
R_VERSIONS = DEPENDENCIES_TESTDATA_DIR / "r_versions.json"
QUARTO_DOWNLOAD = DEPENDENCIES_TESTDATA_DIR / "quarto_download.json"
QUARTO_PRERELEASE = DEPENDENCIES_TESTDATA_DIR / "quarto_prerelease.json"
QUARTO_PREVIOUS_VERSIONS = DEPENDENCIES_TESTDATA_DIR / "quarto_download-older.yml"


PRODUCT_TESTDATA_DIR = Path(os.path.dirname(__file__)) / "image" / "posit_products" / "testdata"
DOWNLOADS_JSON = PRODUCT_TESTDATA_DIR / "downloads.json"
CONNECT_DAILY = PRODUCT_TESTDATA_DIR / "connect_latest-packages.json"
PACKAGE_MANAGER_PREVIEW = PRODUCT_TESTDATA_DIR / "rstudio-pm-main-latest.txt"
PACKAGE_MANAGER_DAILY = PRODUCT_TESTDATA_DIR / "rstudio-pm-rc-latest.txt"
WORKBENCH_DAILY = PRODUCT_TESTDATA_DIR / "workbench_index.json"


@pytest.fixture
def common_image_variants_objects() -> list[dict[str, Any]]:
    """Return pure python objects as the default image variants for testing."""
    return [
        ImageVariant(name="Standard", extension="std", tagDisplayName="std", primary=True),
        ImageVariant(name="Minimal", extension="min", tagDisplayName="min"),
    ]


@pytest.fixture
def common_image_variants(common_image_variants_objects) -> list[dict[str, Any]]:
    """Return pure python objects as the default image variants for testing."""
    return [variant.model_dump() for variant in common_image_variants_objects]


class FakeJSONDecodeError(requests.exceptions.JSONDecodeError):
    def __init__(self):
        super().__init__("Expected error", "", 0)


def patch_testdata_response(url: str):
    mock_response = MagicMock()

    # Mock responses for dependencies
    if url == dependencies_const.UV_PYTHON_DOWNLOADS_JSON_URL:
        mock_response.json.return_value = json.loads(PYTHON_STANDALONE.read_text())
    elif url == dependencies_const.R_VERSIONS_URL:
        mock_response.json.return_value = json.loads(R_VERSIONS.read_text())
    elif url == dependencies_const.QUARTO_DOWNLOAD_URL:
        mock_response.json.return_value = json.loads(QUARTO_DOWNLOAD.read_text())
    elif url == dependencies_const.QUARTO_PRERELEASE_URL:
        mock_response.json.return_value = json.loads(QUARTO_PRERELEASE.read_text())
    elif url == dependencies_const.QUARTO_PREVIOUS_VERSIONS_URL:
        mock_response.json.side_effect = FakeJSONDecodeError
        mock_response.text = QUARTO_PREVIOUS_VERSIONS.read_text()
    # Mock responses for Posit products
    elif url == product_const.DOWNLOADS_JSON_URL:
        mock_response.json.return_value = json.loads(DOWNLOADS_JSON.read_text())
    elif url == product_const.CONNECT_DAILY_URL:
        mock_response.json.return_value = json.loads(CONNECT_DAILY.read_text())
    elif url == product_const.PACKAGE_MANAGER_PREVIEW_URL:
        mock_response.json.side_effect = FakeJSONDecodeError
        mock_response.text = PACKAGE_MANAGER_PREVIEW.read_text()
    elif url == product_const.PACKAGE_MANAGER_DAILY_URL:
        mock_response.json.side_effect = FakeJSONDecodeError
        mock_response.text = PACKAGE_MANAGER_DAILY.read_text()
    elif url == product_const.WORKBENCH_DAILY_URL:
        mock_response.json.return_value = json.loads(WORKBENCH_DAILY.read_text())
    # Default mock response for unknown URLs
    else:
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError
    return mock_response


@pytest.fixture(scope="function")
def disable_requests_caching(mocker):
    return mocker.patch("posit_bakery.util.CachedSession", spec=requests.Session)


@pytest.fixture(scope="function")
def patch_requests_get(disable_requests_caching):
    disable_requests_caching.return_value.get = patch_testdata_response
    return disable_requests_caching


@pytest.fixture()
def ghcr_package_versions_data():
    """Return the GHCR package versions test data as a dictionary."""
    return GHCRPackageVersions(versions=json.loads(GHCR_PACKAGE_VERSIONS.read_text()))
