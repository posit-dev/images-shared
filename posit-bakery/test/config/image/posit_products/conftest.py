import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from posit_bakery.config.image.posit_product import const

TESTDATA_DIR = Path(os.path.dirname(__file__)) / "testdata"
DOWNLOADS_JSON = TESTDATA_DIR / "downloads.json"
CONNECT_DAILY = TESTDATA_DIR / "connect_latest-packages.json"
PACKAGE_MANAGER_PREVIEW = TESTDATA_DIR / "rstudio-pm-main-latest.txt"
PACKAGE_MANAGER_DAILY = TESTDATA_DIR / "rstudio-pm-rc-latest.txt"
WORKBENCH_DAILY = TESTDATA_DIR / "workbench_index.json"


class FakeJSONDecodeError(requests.exceptions.JSONDecodeError):
    def __init__(self):
        super().__init__("Expected error", "", 0)


def patch_testdata_response(url: str):
    mock_response = MagicMock()
    if url == const.DOWNLOADS_JSON_URL:
        mock_response.json.return_value = json.loads(DOWNLOADS_JSON.read_text())
    elif url == const.CONNECT_DAILY_URL:
        mock_response.json.return_value = json.loads(CONNECT_DAILY.read_text())
    elif url == const.PACKAGE_MANAGER_PREVIEW_URL:
        mock_response.json.side_effect = FakeJSONDecodeError
        mock_response.text = PACKAGE_MANAGER_PREVIEW.read_text()
    elif url == const.PACKAGE_MANAGER_DAILY_URL:
        mock_response.json.side_effect = FakeJSONDecodeError
        mock_response.text = PACKAGE_MANAGER_DAILY.read_text()
    elif url == const.WORKBENCH_DAILY_URL:
        mock_response.json.return_value = json.loads(WORKBENCH_DAILY.read_text())
    else:
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError
    return mock_response


@pytest.fixture(scope="function")
def disable_requests_caching(mocker):
    return mocker.patch("posit_bakery.config.image.posit_product.main.CachedSession", spec=requests.Session)


@pytest.fixture(scope="function")
def patch_requests_get(disable_requests_caching):
    disable_requests_caching.return_value.get = patch_testdata_response
    return disable_requests_caching
