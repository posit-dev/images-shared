import os
from pathlib import Path

import pytest


TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))

TOML_BASIC = """name = "basic"

[section]
key = "value"
"""


@pytest.fixture
def toml_basic_str():
    return TOML_BASIC


@pytest.fixture
def toml_basic_file(tmp_path, toml_basic_str):
    filepath = tmp_path / "basic.toml"
    with open(filepath, "w") as f:
        f.write(toml_basic_str)
    return filepath


@pytest.fixture(scope="session")
def test_resource_path():
    return TEST_DIRECTORY / "resources"


@pytest.fixture(scope="session")
def test_suite_basic_context(test_resource_path):
    return test_resource_path / "basic"


@pytest.fixture(scope="session")
def test_suite_basic_config_file(test_suite_basic_context):
    return test_suite_basic_context / "config.toml"
