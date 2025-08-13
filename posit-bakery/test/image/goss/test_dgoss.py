import json
from pathlib import Path
from unittest.mock import patch, call

import pytest

from posit_bakery.image import DGossSuite
from posit_bakery.image.goss.dgoss import DGossCommand

pytestmark = [
    pytest.mark.unit,
    pytest.mark.goss,
]


class TestDGossCommand:
    def test_init(self, basic_standard_image_target):
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
        assert dgoss_command.dgoss_environment == expected_env

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


class TestDGossSuite:
    def test_init(self, basic_unified_config_obj):
        """Test that DGossSuite initializes with the correct attributes."""
        dgoss_suite = DGossSuite(basic_unified_config_obj.base_path, basic_unified_config_obj.targets)
        assert dgoss_suite.context == basic_unified_config_obj.base_path
        assert dgoss_suite.image_targets == basic_unified_config_obj.targets
        assert len(dgoss_suite.dgoss_commands) == 2

    @pytest.mark.slow
    def test_run(self, basic_unified_tmpconfig):
        """Test that DGossSuite run executes the DGoss commands."""
        for target in basic_unified_tmpconfig.targets:
            target.build()

        dgoss_suite = DGossSuite(basic_unified_tmpconfig.base_path, basic_unified_tmpconfig.targets)

        report_collection, errors = dgoss_suite.run()

        assert errors is None
        assert len(report_collection.test_failures) == 0
        assert len(report_collection.get("test-image")) == 2
        for target in dgoss_suite.image_targets:
            results_file = target.context.base_path / "results" / "dgoss" / target.image_name / f"{target.uid}.json"
            assert results_file.exists()
            with open(results_file) as f:
                report = json.load(f)
