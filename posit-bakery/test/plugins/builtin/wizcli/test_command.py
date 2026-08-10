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

    def test_command_cli_policies_projects_override_tool_options(self, basic_standard_image_target):
        """Test that CLI policies/projects win over bakery.yaml tool_options."""
        from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            tool_options=WizCLIOptions(projects=["yaml-proj"], policies=["yaml-pol"]),
            policies="cli-pol-1,cli-pol-2",
            projects="cli-proj",
        )
        command_str = " ".join(cmd.command)
        assert "cli-pol-1,cli-pol-2" in command_str
        assert "yaml-pol" not in command_str
        assert "cli-proj" in command_str
        assert "yaml-proj" not in command_str

    def test_command_policies_projects_fall_back_to_tool_options(self, basic_standard_image_target):
        """Test that policies/projects come from tool_options when no CLI value is given."""
        from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            tool_options=WizCLIOptions(projects=["yaml-proj"], policies=["yaml-pol"]),
        )
        command_str = " ".join(cmd.command)
        assert "yaml-pol" in command_str
        assert "yaml-proj" in command_str

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

    def test_scan_name_format(self, basic_standard_image_target):
        """Test that scan_name follows the Version-OS-Variant-platform format."""
        from unittest.mock import patch

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            tv = basic_standard_image_target.tag_template_values
            expected_suffix = "-".join(part for part in [tv["Version"], tv["OS"], tv["Variant"]] if part)
            assert cmd.scan_name == f"{basic_standard_image_target.image_name}:{expected_suffix}-amd64"
            assert "--name" in cmd.command
            assert cmd.scan_name in cmd.command

    def test_scan_name_in_command(self, basic_standard_image_target):
        """Test that --name flag uses scan_name."""
        from unittest.mock import patch

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "arm64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            idx = cmd.command.index("--name")
            assert cmd.command[idx + 1].endswith("-arm64")

    def test_scan_tags_present(self, basic_standard_image_target):
        """Test that auto-generated scan tags are emitted in the command."""
        from unittest.mock import patch

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            tags_in_command = [cmd.command[i + 1] for i, arg in enumerate(cmd.command) if arg == "--tags"]
            tag_keys = [t.split("=")[0] for t in tags_in_command]
            assert "product" in tag_keys
            assert "version" in tag_keys
            assert "channel" in tag_keys
            assert "platform" in tag_keys

    def test_scan_tags_user_tags_appended(self, basic_standard_image_target):
        """Test that user-supplied tags are emitted after auto-generated ones."""
        from posit_bakery.plugins.builtin.wizcli.options import WizCLIOptions
        from unittest.mock import patch

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch("posit_bakery.plugins.builtin.wizcli.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
                tool_options=WizCLIOptions(tags=["team=platform"]),
            )
            tags_in_command = [cmd.command[i + 1] for i, arg in enumerate(cmd.command) if arg == "--tags"]
            assert "team=platform" in tags_in_command
            # Auto tags appear before user tags
            auto_idx = next(i for i, t in enumerate(tags_in_command) if t.startswith("product="))
            user_idx = tags_in_command.index("team=platform")
            assert auto_idx < user_idx

    def test_scan_context_id_defaults_to_monthly(self, basic_standard_image_target):
        """Test that scan-context-id defaults to a month-stripped release context."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        idx = cmd.command.index("--scan-context-id")
        assert cmd.command[idx + 1] == cmd.default_scan_context_id
        # Should be image-name + stripped version, not the full uid
        assert cmd.command[idx + 1].startswith(basic_standard_image_target.image_name + "-")

    def test_scan_context_id_dev_uses_channel(self, basic_standard_image_target):
        """Test that dev builds use per-channel context ID."""
        from unittest.mock import PropertyMock, patch
        from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum

        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        with patch.object(
            type(basic_standard_image_target),
            "release_channel",
            new_callable=PropertyMock,
            return_value=ReleaseChannelEnum.DAILY,
        ):
            cmd = WizCLICommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            idx = cmd.command.index("--scan-context-id")
            assert cmd.command[idx + 1] == f"{basic_standard_image_target.image_name}-daily"

    def test_scan_context_id_explicit_override(self, basic_standard_image_target):
        """Test that an explicit scan_context_id overrides the uid default."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "wizcli"
        cmd = WizCLICommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            scan_context_id="my-custom-context",
        )
        idx = cmd.command.index("--scan-context-id")
        assert cmd.command[idx + 1] == "my-custom-context"

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
