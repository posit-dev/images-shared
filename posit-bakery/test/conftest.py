import datetime
import os
import shutil
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from ruamel.yaml import YAML
from pytest_mock import MockFixture

# Discover plugins before any config models are used. This registers tool options
# (e.g., GossOptions) and rebuilds config models with proper discriminated unions.
from posit_bakery.plugins.registry import discover_plugins

discover_plugins()

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


@pytest.fixture(autouse=True)
def patch_temporary_directory(request, tmp_path):
    """Patch the repository revision to return a fixed value."""
    if "disable_patch_temporary_directory" not in request.keywords:
        from posit_bakery.settings import SETTINGS

        SETTINGS.temporary_storage = tmp_path


@pytest.fixture(autouse=True)
def _disable_image_build_cache(request, mocker: MockFixture):
    """Disable Docker layer caching for image_build tests.

    Ensures templates and macros are tested end-to-end without stale layers.
    """
    if not any(m.name == "image_build" for m in request.node.iter_markers()):
        return

    from posit_bakery.image.image_target import ImageTarget
    from posit_bakery.image.bake import BakePlan

    original_it_build = ImageTarget.build
    original_bp_build = BakePlan.build

    def it_build_uncached(self, *args, cache=False, **kwargs):
        return original_it_build(self, *args, cache=cache, **kwargs)

    def bp_build_uncached(self, *args, cache=False, **kwargs):
        return original_bp_build(self, *args, cache=cache, **kwargs)

    mocker.patch.object(ImageTarget, "build", it_build_uncached)
    mocker.patch.object(BakePlan, "build", bp_build_uncached)


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


def _isolate_registry_namespace(bakery_yaml_path: Path, suffix: str):
    """Rewrite registry namespaces in a bakery.yaml to include a unique suffix.

    This prevents image tag collisions when multiple tests build from the
    same suite concurrently (e.g., under pytest-xdist).
    """
    yaml = YAML()
    yaml.preserve_quotes = True
    data = yaml.load(bakery_yaml_path)
    for reg in data.get("registries", []):
        ns = reg.get("namespace")
        reg["namespace"] = f"{ns}/t-{suffix}" if ns else f"t-{suffix}"
    yaml.dump(data, bakery_yaml_path)


@pytest.fixture
def get_tmpcontext(request, tmpdir, get_context):
    """Return a function that can get a temporary copy of a test suite context by name.

    For image_build tests (which build real Docker images), each copy gets a
    unique registry namespace suffix to prevent image tag collisions under
    pytest-xdist.
    """
    builds_images = any(m.name == "image_build" for m in request.node.iter_markers())
    suffix = uuid.uuid4().hex[:8] if builds_images else None
    created = set()

    def _get_tmpcontext(suite_name: str) -> Path:
        tmpcontext = Path(tmpdir) / suite_name
        if suite_name not in created:
            tmpcontext.mkdir(parents=True, exist_ok=True)
            shutil.copytree(get_context(suite_name), tmpcontext, dirs_exist_ok=True)
            if suffix:
                _isolate_registry_namespace(tmpcontext / "bakery.yaml", suffix)
            created.add(suite_name)
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
