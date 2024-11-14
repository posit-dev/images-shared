import os
from pathlib import Path

import pytest


TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture
def toml_basic_str():
    """Return a basic TOML document as a string"""
    return """name = "basic"

[section]
key = "value"
"""


@pytest.fixture
def toml_basic_file(tmp_path, toml_basic_str):
    """Return a basic TOML document as a filepath"""
    filepath = tmp_path / "basic.toml"
    with open(filepath, "w") as f:
        f.write(toml_basic_str)
    return filepath


@pytest.fixture(scope="session")
def test_resource_path():
    """Return the path to the test resources directory"""
    return TEST_DIRECTORY / "resources"


@pytest.fixture(scope="session")
def test_suite_basic_context(test_resource_path):
    """Return the path to the basic test suite context"""
    return test_resource_path / "basic"


@pytest.fixture(scope="session")
def test_suite_basic_config_file(test_suite_basic_context):
    """Return the path to the basic test suite config.toml file"""
    return test_suite_basic_context / "config.toml"


@pytest.fixture
def test_suite_basic_config_obj(test_suite_basic_config_file):
    """Return a Config object loaded from basic test suite config.toml file"""
    from posit_bakery.models.config import Config
    return Config.load_file(test_suite_basic_config_file)
