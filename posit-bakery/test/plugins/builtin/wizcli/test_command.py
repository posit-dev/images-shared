from unittest.mock import patch

import pytest
from pydantic import ValidationError

from posit_bakery.plugins.builtin.wizcli.command import WizCLICommand

pytestmark = [
    pytest.mark.unit,
    pytest.mark.wizcli,
]


class TestWizCLICommand:
    def test_from_image_target_basic(self, basic_standard_image_target):
        """Test basic initialization from an image target."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert cmd.image_target == basic_standard_image_target
        assert str(basic_standard_image_target.containerfile) in cmd.command
        assert "--no-color" in cmd.command
        assert "--no-style" in cmd.command
        assert "--json-output-file" in " ".join(cmd.command)

    def test_command_includes_dockerfile(self, basic_standard_image_target):
        """Test that --dockerfile is set to the target's containerfile."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        idx = cmd.command.index("--dockerfile")
        assert cmd.command[idx + 1] == str(basic_standard_image_target.containerfile)

    def test_command_with_cli_options(self, basic_standard_image_target):
        """Test that CLI options are passed through to the command."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            disabled_scanners="Secret,Malware",
            driver="mount",
            timeout="30m",
            no_publish=True,
        )
        assert "--disabled-scanners" in cmd.command
        assert "Secret,Malware" in cmd.command
        assert "--driver" in cmd.command
        assert "mount" in cmd.command
        assert "--timeout" in cmd.command
        assert "30m" in cmd.command
        assert "--no-publish" in cmd.command

    def test_command_with_tool_options(self, basic_standard_image_target):
        """Test that ToolOptions fields are included in the command."""
        from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            tool_options=WizCLIOptions(
                projects=["proj-1", "proj-2"],
                policies=["pol-1"],
                tags=["team=platform"],
                scanOsManagedLibraries=True,
                scanGoStandardLibrary=False,
            ),
        )
        command_str = " ".join(cmd.command)
        assert "--projects" in command_str
        assert "proj-1,proj-2" in command_str
        assert "--policies" in command_str
        assert "pol-1" in command_str
        assert "--tags" in command_str
        assert "team=platform" in command_str
        assert "--scan-os-managed-libraries=true" in command_str
        assert "--scan-go-standard-library=false" in command_str

    def test_command_with_auth_options(self, basic_standard_image_target):
        """Test that auth CLI options are passed through."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            client_id="my-id",
            client_secret="my-secret",
        )
        assert "--client-id" in cmd.command
        assert "my-id" in cmd.command
        assert "--client-secret" in cmd.command
        assert "my-secret" in cmd.command

    def test_command_with_device_code_flags(self, basic_standard_image_target):
        """Test that boolean auth flags are included when set."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            use_device_code=True,
            no_browser=True,
        )
        assert "--use-device-code" in cmd.command
        assert "--no-browser" in cmd.command

    def test_validate_no_wizcli_bin(self, basic_standard_image_target):
        """Test that validation fails if wizcli binary cannot be found."""
        with patch("posit_bakery.plugins.builtin.wizcli.command.find_wizcli_bin") as mock:
            mock.return_value = None
            with pytest.raises(ValidationError, match="wizcli binary path must be specified"):
                results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
                WizCLICommand.from_image_target(
                    image_target=basic_standard_image_target,
                    results_dir=results_dir,
                )
