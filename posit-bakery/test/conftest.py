import os
from pathlib import Path

import pytest


TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture
def resource_path():
    return TEST_DIRECTORY / "resources"
