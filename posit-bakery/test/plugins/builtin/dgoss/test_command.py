import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from posit_bakery.config.dependencies import PythonDependencyVersions, RDependencyVersions
from posit_bakery.plugins.builtin.dgoss.command import DGossCommand, find_dgoss_bin
from posit_bakery.image.image_metadata import MetadataFile

pytestmark = [
    pytest.mark.unit,
    pytest.mark.goss,
]

DGOSS_TESTDATA_DIR = (Path(__file__).parent / "testdata").absolute()


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
            "IMAGE_VARIANT": basic_standard_image_target.image_variant.name,
            "IMAGE_OS": basic_standard_image_target.image_os.name,
            "IMAGE_OS_NAME": basic_standard_image_target.image_os.buildOS.name,
            "IMAGE_OS_VERSION": basic_standard_image_target.image_os.buildOS.version,
            "IMAGE_OS_FAMILY": basic_standard_image_target.image_os.buildOS.family,
            "IMAGE_OS_CODENAME": basic_standard_image_target.image_os.buildOS.codename,
        }
        assert dgoss_command.image_environment == expected_env

    def test_volume_mounts(self, basic_standard_image_target):
        """Test that DGossCommand volume_mounts returns the expected volume mounts."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_mounts = [
            (str(basic_standard_image_target.context.version_path.resolve()), "/tmp/version"),
            (str(basic_standard_image_target.context.image_path.resolve()), "/tmp/image"),
            (str(basic_standard_image_target.context.base_path.resolve()), "/tmp/project"),
        ]
        assert dgoss_command.volume_mounts == expected_mounts

    def test_validate_no_dgoss(self, basic_standard_image_target):
        """Test that DGossCommand validate checks the test path."""
        with patch("posit_bakery.plugins.builtin.dgoss.command.find_dgoss_bin") as mock_find_dgoss_bin:
            mock_find_dgoss_bin.return_value = None
            with pytest.raises(ValidationError, match="dgoss binary path must be specified"):
                DGossCommand.from_image_target(image_target=basic_standard_image_target)

    def test_validate_no_test_path(self, get_tmpconfig):
        """Test that DGossCommand validate raises an error if the test path does not exist."""
        basic_tmpconfig = get_tmpconfig("basic")
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
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "--init",
            basic_standard_image_target.ref(),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command

    def test_command_build_args_env_vars(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        basic_standard_image_target.image_version.isMatrixVersion = True
        basic_standard_image_target.image_version.dependencies = [
            PythonDependencyVersions(dependency="python", versions=["3.13.7"]),
            RDependencyVersions(dependency="R", versions=["4.3.3"]),
        ]
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "-e",
            "BUILD_ARG_PYTHON_VERSION=3.13.7",
            "-e",
            "BUILD_ARG_R_VERSION=4.3.3",
            "--init",
            basic_standard_image_target.ref(),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command

    def test_command_with_platform_option(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target, platform="linux/arm64")
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "--platform",
            "linux/arm64",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "--init",
            basic_standard_image_target.ref("linux/arm64"),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command

    def test_command_with_runtime_options(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        basic_standard_image_target.image_variant.options[0].runtimeOptions = "--privileged"
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "--init",
            "--privileged",
            basic_standard_image_target.ref(),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command

    def test_command_with_build_metadata(self, basic_standard_image_target):
        """Test that DGossCommand command returns the expected command."""
        basic_standard_image_target.load_build_metadata_from_file(
            MetadataFile.load(DGOSS_TESTDATA_DIR / "basic_metadata.json")
        )
        assert (
            basic_standard_image_target.ref()
            == "docker.io/posit/test-image:1.0.0@sha256:80a50319320bf34740251482b7c06bf6dddb52aa82ea4cbffa812ed2fafaa0b9"
        )
        dgoss_command = DGossCommand.from_image_target(image_target=basic_standard_image_target)
        expected_command = [
            find_dgoss_bin(basic_standard_image_target.context),
            "run",
            "-v",
            f"{str(basic_standard_image_target.context.version_path.resolve())}:/tmp/version",
            "-v",
            f"{str(basic_standard_image_target.context.image_path.resolve())}:/tmp/image",
            "-v",
            f"{str(basic_standard_image_target.context.base_path.resolve())}:/tmp/project",
            "-e",
            "IMAGE_VERSION=1.0.0",
            "-e",
            "IMAGE_VERSION_MOUNT=/tmp/version",
            "-e",
            "IMAGE_MOUNT=/tmp/image",
            "-e",
            "PROJECT_MOUNT=/tmp/project",
            "-e",
            "IMAGE_VARIANT=Standard",
            "-e",
            "IMAGE_OS=Ubuntu\ 22.04",
            "-e",
            "IMAGE_OS_NAME=ubuntu",
            "-e",
            "IMAGE_OS_CODENAME=jammy",
            "-e",
            "IMAGE_OS_FAMILY=debian",
            "-e",
            "IMAGE_OS_VERSION=22.04",
            "--init",
            basic_standard_image_target.ref(),
            *basic_standard_image_target.image_variant.get_tool_option("goss").command.split(),
        ]
        assert dgoss_command.command == expected_command
