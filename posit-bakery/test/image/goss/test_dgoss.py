import json
import shutil
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from posit_bakery.image import DGossSuite
from posit_bakery.image.goss.dgoss import DGossCommand, find_dgoss_bin

pytestmark = [
    pytest.mark.unit,
    pytest.mark.goss,
]


class TestDGossCommand:
    def test_from_image_target(self, basic_standard_image_target):
        """Test that DGossCommand initializes with the correct attributes."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        assert dgoss_command.image_target == basic_standard_image_target
        assert basic_standard_image_target.context.version_path / "test" == dgoss_command.test_path
        assert dgoss_command.wait == 1

    def test_dgoss_environment(self, basic_standard_image_target):
        """Test that DGossCommand dgoss_environment returns the expected environment variables."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_env = {
            "GOSS_FILES_PATH": str(basic_standard_image_target.context.version_path / "test"),
            "GOSS_SLEEP": "1",
            "GOSS_OPTS": "--format json --no-color",
        }
        for key, value in expected_env.items():
            assert dgoss_command.dgoss_environment[key] == value, (
                f"Expected {key} to be {value}, got {dgoss_command.dgoss_environment[key]}"
            )

    def test_image_environment(self, basic_standard_image_target):
        """Test that DGossCommand image_environment returns the expected environment variables."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_env = {
            "IMAGE_VERSION": basic_standard_image_target.image_version.name,
            "IMAGE_VERSION_MOUNT": "/tmp/version",
            "IMAGE_MOUNT": "/tmp/image",
            "PROJECT_MOUNT": "/tmp/project",
            "IMAGE_TYPE": basic_standard_image_target.image_variant.name,
            "IMAGE_VARIANT": basic_standard_image_target.image_variant.name,
            "IMAGE_OS": basic_standard_image_target.image_os.name,
        }
        assert dgoss_command.image_environment == expected_env

    def test_volume_mounts(self, basic_standard_image_target):
        """Test that DGossCommand volume_mounts returns the expected volume mounts."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_mounts = [
            (str(basic_standard_image_target.context.version_path.absolute()), "/tmp/version"),
            (str(basic_standard_image_target.context.image_path.absolute()), "/tmp/image"),
            (str(basic_standard_image_target.context.base_path.absolute()), "/tmp/project"),
        ]
        assert dgoss_command.volume_mounts == expected_mounts

    def test_validate_no_dgoss(self, basic_standard_image_target):
        """Test that DGossCommand validate checks the test path."""
        with patch("posit_bakery.image.goss.dgoss.find_dgoss_bin") as mock_find_dgoss_bin:
            mock_find_dgoss_bin.return_value = None
            with pytest.raises(ValidationError, match="dgoss binary path must be specified"):
                DGossCommand.from_image_target(image_target=basic_standard_image_target)

    def test_validate_no_test_path(self, basic_tmpconfig):
        """Test that DGossCommand validate raises an error if the test path does not exist."""
        shutil.rmtree(basic_tmpconfig.targets[0].context.version_path / "test")
        with pytest.raises(ValidationError, match="No test directory was found"):
            DGossCommand.from_image_target(image_target=basic_tmpconfig.targets[0])

    def test_command(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.absolute())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.absolute())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.absolute())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_TYPE=Standard",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu 22.04",
            "--init",
            basic_standard_image_target.tags[0],
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command


class TestDGossSuite:
    def test_init(self, basic_config_obj):
        """Test that DGossSuite initializes with the correct attributes."""
        dgoss_suite = DGossSuite(basic_config_obj.base_path, basic_config_obj.targets)
        assert dgoss_suite.context == basic_config_obj.base_path
        assert dgoss_suite.image_targets == basic_config_obj.targets
        assert len(dgoss_suite.dgoss_commands) == 2

    @pytest.mark.slow
    def test_run(self, basic_tmpconfig):
        """Test that DGossSuite run executes the DGoss commands."""
        basic_tmpconfig.build_targets()

        dgoss_suite = DGossSuite(basic_tmpconfig.base_path, basic_tmpconfig.targets)

        report_collection, errors = dgoss_suite.run()

        assert errors is None
        assert len(report_collection.test_failures) == 0
        assert len(report_collection.get("test-image")) == 2
        for target in dgoss_suite.image_targets:
            results_file = target.context.base_path / "results" / "dgoss" / target.image_name / f"{target.uid}.json"
            assert results_file.exists()
            with open(results_file) as f:
                json.load(f)
