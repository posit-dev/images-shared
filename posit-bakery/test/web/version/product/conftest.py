import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

from posit_bakery.web.version.product.const import DOWNLOADS_JSON_URL, CONNECT_DAILY_URL, PACKAGE_MANAGER_PREVIEW_URL, \
    PACKAGE_MANAGER_DAILY_URL, WORKBENCH_DAILY_URL

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
    if url == DOWNLOADS_JSON_URL:
        mock_response.json.return_value = json.loads(DOWNLOADS_JSON.read_text())
    elif url == CONNECT_DAILY_URL:
        mock_response.json.return_value = json.loads(CONNECT_DAILY.read_text())
    elif url == PACKAGE_MANAGER_PREVIEW_URL:
        mock_response.json.side_effect = FakeJSONDecodeError
        mock_response.text = PACKAGE_MANAGER_PREVIEW.read_text()
    elif url == PACKAGE_MANAGER_DAILY_URL:
        mock_response.json.side_effect = FakeJSONDecodeError
        mock_response.text = PACKAGE_MANAGER_DAILY.read_text()
    elif url == WORKBENCH_DAILY_URL:
        mock_response.json.return_value = json.loads(WORKBENCH_DAILY.read_text())
    else:
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError
    return mock_response


@pytest.fixture
def patch_requests_get(mocker):
    return mocker.patch("requests.get", new=patch_testdata_response)
