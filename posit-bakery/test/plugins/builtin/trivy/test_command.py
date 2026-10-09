from unittest.mock import patch

import pytest
from pydantic import ValidationError

from posit_bakery.plugins.builtin.trivy.command import TrivyCommand

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]


class TestTrivyCommand:
    def test_from_image_target_basic(self, basic_standard_image_target):
        """Test basic initialization from an image target."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert cmd.image_target == basic_standard_image_target
        assert cmd.results_file == results_dir / "test-image" / f"{basic_standard_image_target.uid}.sarif"

    def test_command_includes_format_and_output(self, basic_standard_image_target):
        """Test that --format sarif and --output <results_file> are always present."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert "--format" in cmd.command
        assert cmd.command[cmd.command.index("--format") + 1] == "sarif"
        assert "--output" in cmd.command
        assert cmd.command[cmd.command.index("--output") + 1] == str(cmd.results_file)

    def test_command_ends_with_digest_ref(self, basic_standard_image_target):
        """Test that the last element is the tag-free digest ref for the target platform."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert cmd.command[-1] == basic_standard_image_target.ref(platform=cmd.platform, digest_only=True)

    def test_from_image_target_uses_parent_image_options_when_variant_less(self, no_variant_image_target):
        """Image-level trivy options must apply to images with no `variants:` entry.

        Regression test for posit-dev/images-shared#756, mirroring WizCLICommand's own test.
        """
        assert no_variant_image_target.image_variant is None
        results_dir = no_variant_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=no_variant_image_target,
            results_dir=results_dir,
        )
        assert cmd.tool_options is not None
        assert cmd.tool_options.severity == ["CRITICAL", "HIGH"]
        assert "--severity" in cmd.command
        idx = cmd.command.index("--severity")
        assert cmd.command[idx + 1] == "CRITICAL,HIGH"
        assert "--ignore-unfixed" in cmd.command
        assert "--skip-files" in cmd.command
        assert "--skip-dirs" in cmd.command
        assert "--exit-code" in cmd.command
        assert cmd.command[cmd.command.index("--exit-code") + 1] == "1"

    def test_command_with_cli_severity_overrides_tool_options(self, no_variant_image_target):
        """Test that a CLI severity value wins over bakery.yaml tool_options."""
        results_dir = no_variant_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=no_variant_image_target,
            results_dir=results_dir,
            severity=["LOW"],
            failure_severity=["LOW"],
        )
        command_str = " ".join(cmd.command)
        assert "--severity" in command_str
        idx = cmd.command.index("--severity")
        assert cmd.command[idx + 1] == "LOW"
        assert "CRITICAL,HIGH" not in command_str

    def test_command_skip_files_and_skip_dirs_repeat_flag_not_comma_joined(self, basic_standard_image_target):
        """Test that skip_files/skip_dirs emit one repeated flag per value, not a comma list."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            skip_files=["a", "b"],
            skip_dirs=["/tmp", "/var"],
        )
        assert cmd.command.count("--skip-files") == 2
        assert cmd.command.count("--skip-dirs") == 2
        idx = cmd.command.index("--skip-files")
        assert cmd.command[idx + 1] == "a"
        assert cmd.command[cmd.command.index("--skip-files", idx + 1) + 1] == "b"
        assert "a,b" not in " ".join(cmd.command)

    def test_command_with_ignore_unfixed_and_exit_code(self, basic_standard_image_target):
        """Test that ignore_unfixed and exit_code CLI flags are passed through."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            ignore_unfixed=True,
            exit_code=2,
        )
        assert "--ignore-unfixed" in cmd.command
        assert "--exit-code" in cmd.command
        assert cmd.command[cmd.command.index("--exit-code") + 1] == "2"

    def test_default_scan_platform_uses_host_architecture(self, basic_standard_image_target):
        """With no explicit platform, the scan targets the host platform."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        with patch("posit_bakery.plugins.builtin.trivy.command.SETTINGS") as mock_settings:
            mock_settings.architecture = "amd64"
            cmd = TrivyCommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
            )
            assert cmd.platform == "linux/amd64"

    def test_command_scanners_comma_joined(self, basic_standard_image_target):
        """Test that scanners emit a single comma-joined --scanners flag, like --severity."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            scanners=["vuln", "secret"],
        )
        assert cmd.command[cmd.command.index("--scanners") + 1] == "vuln,secret"

    def test_command_timeout_passed_through(self, basic_standard_image_target):
        """Test that timeout is passed through as a single value, not comma-split."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            timeout="5m0s",
        )
        assert cmd.command[cmd.command.index("--timeout") + 1] == "5m0s"

    def test_command_failure_severity_never_reaches_argv(self, basic_standard_image_target):
        """failure_severity has no trivy CLI equivalent -- it must never appear in argv."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            failure_severity=["CRITICAL"],
        )
        assert "--fail-on-severity" not in cmd.command
        assert "CRITICAL" not in cmd.command

    def test_resolved_failure_severity_cli_wins_over_tool_options(self, no_variant_image_target):
        """An explicit failure_severity wins over bakery.yaml tool_options."""
        results_dir = no_variant_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=no_variant_image_target,
            results_dir=results_dir,
            failure_severity=["CRITICAL"],
        )
        assert cmd.resolved_failure_severity == ["CRITICAL"]

    def test_resolved_failure_severity_falls_back_to_tool_options(self, no_variant_image_target):
        """With no CLI value, resolves to the bakery.yaml failureSeverity."""
        results_dir = no_variant_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=no_variant_image_target,
            results_dir=results_dir,
        )
        assert cmd.resolved_failure_severity == ["HIGH"]

    def test_resolved_failure_severity_none_by_default(self, basic_standard_image_target):
        """With no CLI value and no tool_options.failureSeverity, resolves to None."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert cmd.resolved_failure_severity is None

    def test_failure_severity_outside_severity_rejected(self, basic_standard_image_target):
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        with pytest.raises(ValidationError, match="not in the scanned severities"):
            TrivyCommand.from_image_target(
                image_target=basic_standard_image_target,
                results_dir=results_dir,
                severity=["CRITICAL"],
                failure_severity=["HIGH"],
            )

    def test_failure_severity_within_severity_accepted(self, basic_standard_image_target):
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            severity=["critical", "HIGH"],
            failure_severity=["HIGH"],
        )
        assert cmd.resolved_failure_severity == ["HIGH"]

    def test_failure_severity_unchecked_without_severity(self, basic_standard_image_target):
        """No severity resolved: trivy scans everything, so any gate severity is reachable."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            failure_severity=["LOW"],
        )
        assert cmd.resolved_failure_severity == ["LOW"]
