from pathlib import Path
from typing import List
from unittest.mock import patch, call

import pytest
import python_on_whales
from pytest_mock import MockFixture

from posit_bakery.image.bake import BakePlan
from posit_bakery.image.bake.bake import BakeTarget, BakeGroup

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
def barebones_expected_plan(bake_testdata):
    """Fixture to provide the expected barebones bake plan."""
    return bake_testdata / "barebones_plan.json"


@pytest.fixture
def basic_expected_plan(bake_testdata):
    """Fixture to provide the expected basic bake plan."""
    return bake_testdata / "basic_plan.json"


class TestBakeTarget:
    def test_from_image_target(self, patch_datetime_now, basic_standard_image_target):
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

    @pytest.mark.parametrize(
        "expected_plan,config_obj",
        [
            pytest.param("barebones_expected_plan", "barebones_unified_config_obj", id="barebones"),
            pytest.param("basic_expected_plan", "basic_unified_config_obj", id="basic"),
        ],
    )
    def test_from_image_targets(
        self, request, patch_datetime_now, patch_repository_revision, expected_plan, config_obj
    ):
        """Test that barebones bake plan generates as expected."""
        expected_plan = request.getfixturevalue(expected_plan)
        config_obj = request.getfixturevalue(config_obj)

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)
        output = plan.model_dump_json(indent=2, exclude_none=True)

        assert expected_plan.read_text().strip() == output

    @pytest.mark.parametrize(
        "expected_plan,config_obj",
        [
            pytest.param("barebones_expected_plan", "barebones_unified_tmpconfig", id="barebones"),
            pytest.param("basic_expected_plan", "basic_unified_tmpconfig", id="basic"),
        ],
    )
    def test_write_remove(self, request, patch_datetime_now, patch_repository_revision, expected_plan, config_obj):
        """Test that barebones bake plan generates as expected."""
        expected_plan = request.getfixturevalue(expected_plan)
        config_obj = request.getfixturevalue(config_obj)

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)
        assert not plan.bake_file.is_file()
        plan.write()

        assert plan.bake_file.is_file()
        assert expected_plan.read_text().strip() == plan.bake_file.read_text()

        plan.remove()
        assert not plan.bake_file.is_file()

    @pytest.mark.parametrize(
        "config_obj",
        [
            pytest.param("barebones_unified_config_obj", id="barebones"),
            pytest.param("basic_unified_config_obj", id="basic"),
        ],
    )
    def test_build_args(
        self,
        request,
        patch_os_getcwd,
        patch_os_chdir,
        patch_bakeplan_write,
        patch_bakeplan_remove,
        config_obj,
    ):
        """Test that the build arguments are constructed correctly."""
        config_obj = request.getfixturevalue(config_obj)

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)

        expected_build_args = {
            "files": [str(plan.bake_file.name)],
            "load": True,
            "push": False,
            "cache": True,
        }

        with patch("python_on_whales.docker.buildx.bake") as mock_bake:
            plan.build()
            mock_bake.assert_called_once_with(**expected_build_args)

        patch_os_getcwd.assert_called_once()
        patch_os_chdir.assert_has_calls([call(plan.context), call("/cwd")])
        patch_bakeplan_write.assert_called_once()
        patch_bakeplan_remove.assert_called_once()

    @pytest.mark.slow
    @pytest.mark.parametrize(
        "config_obj",
        [
            pytest.param("barebones_unified_tmpconfig", id="barebones"),
            pytest.param("basic_unified_tmpconfig", id="basic"),
        ],
    )
    def test_build(
        self,
        request,
        config_obj,
    ):
        """Test that the build arguments are constructed correctly."""
        config_obj = request.getfixturevalue(config_obj)

        plan = BakePlan.from_image_targets(config_obj.base_path, config_obj.targets)

        plan.build()

        for bake_target in plan.target.values():
            for tag in bake_target.tags:
                assert python_on_whales.docker.image.exists(tag)
                python_on_whales.docker.image.remove(tag)
