import datetime
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pytest_mock import MockFixture

from posit_bakery.config import BakeryConfig

TEST_DIRECTORY = Path(os.path.dirname(os.path.realpath(__file__)))

CONST_DATETIME_NOW = datetime.datetime(2025, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)


@pytest.fixture
def datetime_now_value():
    """Return a fixed datetime for testing."""
    return CONST_DATETIME_NOW


@pytest.fixture(autouse=True)
def patch_datetime_now(request, mocker: MockFixture, datetime_now_value):
    """Mock datetime.now() to return a fixed datetime for testing."""
    if "disable_patch_datetime_now" not in request.keywords:
        import posit_bakery.image.image_target

        for patch_path in [
            "posit_bakery.image.image_target.datetime",
            "posit_bakery.registry_management.ghcr.models.datetime",
        ]:
            mocked_datetime = mocker.patch(
                patch_path,
            )
            mock_datetime_now = MagicMock(spec=datetime_now_value)
            mocked_datetime.now = mock_datetime_now
            mock_datetime_now.return_value = datetime_now_value
            mock_datetime_now.isoformat.return_value = datetime_now_value.isoformat()


@pytest.fixture
def revision_value():
    """Return a fixed revision string for testing."""
    return "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


@pytest.fixture(autouse=True)
def patch_repository_revision(request, mocker: MockFixture, revision_value):
    """Patch the repository revision to return a fixed value."""
    if "disable_patch_revision" not in request.keywords:
        import posit_bakery.config.repository

        mocker.patch.object(
            posit_bakery.config.repository.Repository,
            "revision",
            revision_value,
        )


@pytest.fixture(scope="session")
def project_path():
    """Return the path to the test directory"""
    return TEST_DIRECTORY.parent


@pytest.fixture(scope="session")
def test_path():
    """Return the path to the test directory"""
    return TEST_DIRECTORY


@pytest.fixture(scope="session")
def resource_path():
    """Return the path to the test resources directory"""
    return TEST_DIRECTORY / "resources"


@pytest.fixture(scope="session")
def testdata_path():
    """Return the path to the test data directory"""
    return TEST_DIRECTORY / "testdata"


@pytest.fixture
def get_context(resource_path):
    """Return a function that can get the path to a test suite context by name"""

    def _get_context(suite_name: str) -> Path:
        return resource_path / suite_name

    return _get_context


@pytest.fixture
def get_config_file(get_context):
    """Return a function that can get the path to a test suite bakery.yaml file by name"""

    def _get_config_file(suite_name: str) -> Path:
        return get_context(suite_name) / "bakery.yaml"

    return _get_config_file


@pytest.fixture
def get_config_obj(get_config_file):
    """Return a function that can get a BakeryConfig object by test suite name"""

    def _get_config_obj(suite_name: str) -> BakeryConfig:
        return BakeryConfig(get_config_file(suite_name))

    return _get_config_obj


@pytest.fixture
def get_tmpcontext(tmpdir, get_context):
    """Return a function that can get a temporary copy of a test suite context by name"""

    def _get_tmpcontext(suite_name: str) -> Path:
        tmpcontext = Path(tmpdir) / suite_name
        tmpcontext.mkdir(parents=True, exist_ok=True)
        shutil.copytree(get_context(suite_name), tmpcontext, dirs_exist_ok=True)
        return tmpcontext

    return _get_tmpcontext


@pytest.fixture
def get_tmpconfig(get_tmpcontext):
    """Return a function that can get a temporary copy of a test suite bakery.yaml file by name"""

    def _get_tmpconfig(suite_name: str) -> BakeryConfig:
        return BakeryConfig(get_tmpcontext(suite_name) / "bakery.yaml")

    return _get_tmpconfig


@pytest.fixture
def get_targets(get_config_obj):
    """Return a function that can get the list of ImageTarget objects for a test suite by name"""

    def _get_targets(suite_name: str):
        return get_config_obj(suite_name).targets

    return _get_targets


@pytest.fixture
def get_target_variant(get_config_obj):
    """Return a function that can get an ImageTarget object for a specific variant of a test suite by name"""

    def _get_target_variant(suite_name: str, variant_name: str):
        return [t for t in get_config_obj(suite_name).targets if t.image_variant.name == variant_name]

    return _get_target_variant
