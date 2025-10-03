import os
from pathlib import Path
from unittest.mock import patch, call

import pytest
import python_on_whales
from pytest_mock import MockFixture

from posit_bakery.image.bake import BakePlan
from posit_bakery.image.bake.bake import BakeTarget, BakeGroup
from test.helpers import remove_images, SUCCESS_SUITES

pytestmark = [
    pytest.mark.unit,
    pytest.mark.bake,
]


@pytest.fixture
def patch_bakeplan_write(mocker: MockFixture):
    """Patch the BakePlan write method to prevent file system operations."""
    import posit_bakery.image.bake

    mock_write = mocker.patch.object(
        posit_bakery.image.bake.BakePlan,
        "write",
    )
    yield mock_write


@pytest.fixture
def patch_bakeplan_remove(mocker: MockFixture):
    """Patch the BakePlan remove method to prevent file system operations."""
    import posit_bakery.image.bake

    mock_remove = mocker.patch.object(
        posit_bakery.image.bake.BakePlan,
        "remove",
    )
    yield mock_remove


@pytest.fixture
def bake_testdata():
    """Fixture to provide the path to the bake test data directory."""
    return Path(__file__).parent / "testdata"


@pytest.fixture
def get_expected_plan(bake_testdata):
    """Fixture to provide the expected bake plan."""

    def _get_expected_plan(suite_name: str) -> Path:
        return bake_testdata / f"{suite_name}_plan.json"

    return _get_expected_plan


class TestBakeTarget:
    def test_from_image_target(self, basic_standard_image_target):
        """Test that BakeTarget can be created from an ImageTarget."""
        bake_target = BakeTarget.from_image_target(basic_standard_image_target)
        assert bake_target.image_name == "test-image"
        assert bake_target.image_variant == "Standard"
        assert bake_target.image_os == "Ubuntu 22.04"
        assert bake_target.dockerfile == basic_standard_image_target.containerfile
        assert bake_target.labels == basic_standard_image_target.labels
        assert bake_target.tags == basic_standard_image_target.tags


class TestBakePlan:
    def test_update_groups_new(self):
        """Test that update_groups creates a new group if it doesn't exist."""
        groups = {"default": BakeGroup()}
        BakePlan.update_groups(groups, "new-uid", "new-image", "new-variant")
        assert "new-uid" in groups["default"].targets
        assert "new-image" in groups.keys()
        assert "new-uid" in groups["new-image"].targets
        assert "new-variant" in groups.keys()
        assert "new-uid" in groups["new-variant"].targets

    def test_update_groups_existing_image(self):
        """Test that update_groups appends on existing images."""
        groups = {
            "default": BakeGroup(targets=["existing-uid"]),
            "existing-image": BakeGroup(targets=["existing-uid"]),
            "existing-variant": BakeGroup(targets=["existing-uid"]),
        }
        BakePlan.update_groups(groups, "new-uid", "existing-image", "new-variant")
        assert "existing-uid" in groups["default"].targets
        assert "new-uid" in groups["default"].targets
        assert "existing-uid" in groups["existing-image"].targets
        assert "new-uid" in groups["existing-image"].targets
        assert "existing-uid" in groups["existing-variant"].targets
        assert "new-uid" in groups["new-variant"].targets
        assert "existing-uid" not in groups["new-variant"].targets

    def test_update_groups_existing_variant(self):
        """Test that update_groups appends on existing images."""
        groups = {
            "default": BakeGroup(targets=["existing-uid"]),
            "existing-image": BakeGroup(targets=["existing-uid"]),
            "existing-variant": BakeGroup(targets=["existing-uid"]),
        }
        BakePlan.update_groups(groups, "new-uid", "new-image", "existing-variant")
        assert "existing-uid" in groups["default"].targets
        assert "new-uid" in groups["default"].targets
        assert "existing-uid" not in groups["new-image"].targets
        assert "new-uid" in groups["new-image"].targets
        assert "existing-uid" in groups["existing-variant"].targets
        assert "new-uid" in groups["existing-variant"].targets

    def test_bake_file(self, basic_standard_image_target):
        """Test that the bake file path is constructed correctly."""
        plan = BakePlan.from_image_targets(Path("/path/to/context"), [basic_standard_image_target])
        assert Path("/path/to/context/.bakery-bake.json") == plan.bake_file

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_from_image_targets(self, get_expected_plan, get_config_obj, suite, resource_path):
        """Test that barebones bake plan generates as expected."""
        expected_plan = get_expected_plan(suite)
        config_obj = get_config_obj(suite)

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)
        output = plan.model_dump_json(indent=2, exclude_none=True)

        assert plan.bake_file == resource_path / suite / ".bakery-bake.json"
        assert expected_plan.read_text().strip() == output

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_from_image_targets_alternate_context(
        self, get_expected_plan, get_config_obj, suite, project_path, resource_path
    ):
        """Test that a BakePlan can be loaded in an alternate context directory."""
        expected_plan = get_expected_plan(suite)
        config_obj = get_config_obj(suite)

        original_dir = os.getcwd()
        os.chdir(project_path)  # Change to root directory

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)
        output = plan.model_dump_json(indent=2, exclude_none=True)

        assert plan.bake_file == resource_path / suite / ".bakery-bake.json"
        assert expected_plan.read_text().strip() == output

        os.chdir(original_dir)  # Change back to original directory

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_write_remove(self, get_expected_plan, get_tmpconfig, suite):
        """Test that barebones bake plan generates as expected."""
        expected_plan = get_expected_plan(suite)
        config_obj = get_tmpconfig(suite)

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)
        assert not plan.bake_file.is_file()
        plan.write()

        assert plan.bake_file.is_file()
        assert expected_plan.read_text().strip() == plan.bake_file.read_text()

        plan.remove()
        assert not plan.bake_file.is_file()

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_write_remove(self, get_expected_plan, get_tmpconfig, suite):
        """Test that barebones bake plan generates as expected."""
        expected_plan = get_expected_plan(suite)
        config_obj = get_tmpconfig(suite)

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)
        assert not plan.bake_file.is_file()
        plan.write()

        assert plan.bake_file == config_obj.base_path / ".bakery-bake.json"
        assert plan.bake_file.is_file()
        assert expected_plan.read_text().strip() == plan.bake_file.read_text()

        plan.remove()
        assert not plan.bake_file.is_file()

    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    def test_build_args(
        self,
        patch_os_getcwd,
        patch_os_chdir,
        patch_bakeplan_write,
        patch_bakeplan_remove,
        suite,
        get_config_obj,
    ):
        """Test that the build arguments are constructed correctly."""
        config_obj = get_config_obj(suite)

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)

        expected_build_args = {
            "files": [str(plan.bake_file.name)],
            "load": True,
            "push": False,
            "cache": True,
            "set": {"*.platform": "linux/amd64"},
        }

        with patch("python_on_whales.docker.buildx.bake") as mock_bake:
            plan.build()
            mock_bake.assert_called_once_with(**expected_build_args)

        patch_os_getcwd.assert_called_once()
        patch_os_chdir.assert_has_calls([call(plan.context), call("/cwd")])
        patch_bakeplan_write.assert_called_once()
        patch_bakeplan_remove.assert_called_once()

    @pytest.mark.slow
    @pytest.mark.parametrize("suite", SUCCESS_SUITES)
    @pytest.mark.xdist_group(name="build")
    def test_build(self, suite, get_tmpconfig):
        """Test that the build arguments are constructed correctly."""
        config_obj = get_tmpconfig(suite)

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)

        plan.build()

        for bake_target in plan.target.values():
            for tag in bake_target.tags:
                assert python_on_whales.docker.image.exists(tag)
                for key, value in bake_target.labels.items():
                    meta = python_on_whales.docker.image.inspect(tag)
                    assert key in meta.config.labels
                    assert value == meta.config.labels[key]

        remove_images(config_obj)
