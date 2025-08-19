import os
import shutil
from pathlib import Path

import pytest

from posit_bakery.config import BakeryConfig

TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))


@pytest.fixture(scope="session")
def resource_path():
    """Return the path to the test resources directory"""
    return TEST_DIRECTORY / "resources"


@pytest.fixture(scope="session")
def testdata_path():
    """Return the path to the test data directory"""
    return TEST_DIRECTORY / "testdata"


@pytest.fixture(scope="session")
def basic_context(resource_path):
    """Return the path to the basic test suite context"""
    return resource_path / "basic"


@pytest.fixture(scope="session")
def basic_config_file(basic_context):
    """Return the path to the basic test suite bakery.yaml file"""
    return basic_context / "bakery.yaml"


@pytest.fixture
def basic_config_obj(basic_config_file):
    """Return a BakeryConfig object loaded from basic test suite bakery.yaml file"""
    return BakeryConfig(basic_config_file)


@pytest.fixture
def basic_expected_num_targets(basic_config_obj):
    """Returns the expected number of target builds for the basic suite"""
    count = 0
    for image in basic_config_obj.model.images:
        count += len(image.variants) + len([len(o) for v in image.versions for o in v.os])
    return count


@pytest.fixture
def basic_tmpcontext(tmpdir, basic_context):
    """Return a temporary copy of the basic test suite context"""
    tmpcontext = Path(tmpdir) / "basic"
    tmpcontext.mkdir(parents=True, exist_ok=True)
    shutil.copytree(basic_context, tmpcontext, dirs_exist_ok=True)
    return tmpcontext


@pytest.fixture
def basic_tmpconfig(basic_tmpcontext):
    """Return a temporary copy of the basic test suite bakery.yaml file"""
    return BakeryConfig(basic_tmpcontext / "bakery.yaml")


@pytest.fixture(scope="session")
def barebones_context(resource_path):
    """Return the path to the barebones test suite context"""
    return resource_path / "barebones"


@pytest.fixture(scope="session")
def barebones_config_file(barebones_context):
    """Return the path to the barebones test suite bakery.yaml file"""
    return barebones_context / "bakery.yaml"


@pytest.fixture
def barebones_config_obj(barebones_config_file):
    """Return a BakeryConfig object loaded from basic test suite bakery.yaml file"""
    return BakeryConfig(barebones_config_file)


@pytest.fixture
def barebones_expected_num_variants(barebones_config_obj):
    """Returns the expected number of target builds for the barebones bakery.yaml"""
    count = 0
    for image in barebones_config_obj.model.images:
        count += len(image.variants) + len([len(o) for v in image.versions for o in v.os])
    return count


@pytest.fixture
def barebones_tmpcontext(tmpdir, barebones_context):
    """Return a temporary copy of the barebones test suite context"""
    tmpcontext = Path(tmpdir) / "barebones"
    tmpcontext.mkdir(parents=True, exist_ok=True)
    shutil.copytree(barebones_context, tmpcontext, dirs_exist_ok=True)
    return tmpcontext


@pytest.fixture
def barebones_tmpconfig(barebones_tmpcontext):
    """Return a temporary copy of the barebones test suite bakery.yaml file"""
    return BakeryConfig(barebones_tmpcontext / "bakery.yaml")
