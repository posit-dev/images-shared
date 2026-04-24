import logging
from unittest.mock import patch

import pytest

from posit_bakery.plugins.builtin.hadolint.command import HadolintCommand
from posit_bakery.plugins.builtin.hadolint.options import DEFAULT_IGNORED_RULES, HadolintOptions

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hadolint,
]


class TestHadolintCommand:
    def test_from_image_target_defaults(self, basic_standard_image_target):
        """Test that HadolintCommand initializes with correct defaults."""
        cmd = HadolintCommand.from_image_target(basic_standard_image_target)
        assert cmd.image_target == basic_standard_image_target
        assert cmd.containerfile_path == (
            basic_standard_image_target.context.base_path / basic_standard_image_target.containerfile
        )

    def test_command_includes_format_json(self, basic_standard_image_target):
        """Test that the command always includes --format json."""
        cmd = HadolintCommand.from_image_target(basic_standard_image_target)
        assert "--format" in cmd.command
        idx = cmd.command.index("--format")
        assert cmd.command[idx + 1] == "json"

    def test_command_includes_containerfile(self, basic_standard_image_target):
        """Test that the command ends with the containerfile path."""
        cmd = HadolintCommand.from_image_target(basic_standard_image_target)
        expected_path = str(basic_standard_image_target.context.base_path / basic_standard_image_target.containerfile)
        assert cmd.command[-1] == expected_path

    def test_command_default_failure_threshold(self, basic_standard_image_target):
        """Test that the default failure threshold is 'error' when no options are provided."""
        cmd = HadolintCommand.from_image_target(basic_standard_image_target)
        assert "--failure-threshold" in cmd.command
        idx = cmd.command.index("--failure-threshold")
        assert cmd.command[idx + 1] == "error"

    def test_command_verbose_when_debug(self, basic_standard_image_target):
        """Test that --verbose is included when log level is DEBUG."""
        with patch("posit_bakery.plugins.builtin.hadolint.command.SETTINGS") as mock_settings:
            mock_settings.log_level = logging.DEBUG
            cmd = HadolintCommand.from_image_target(basic_standard_image_target)
            assert "--verbose" in cmd.command

    def test_command_no_verbose_when_info(self, basic_standard_image_target):
        """Test that --verbose is NOT included when log level is INFO."""
        with patch("posit_bakery.plugins.builtin.hadolint.command.SETTINGS") as mock_settings:
            mock_settings.log_level = logging.INFO
            cmd = HadolintCommand.from_image_target(basic_standard_image_target)
            assert "--verbose" not in cmd.command

    def test_command_with_failure_threshold(self, basic_standard_image_target):
        """Test that --failure-threshold is included when set."""
        options = HadolintOptions(failureThreshold="warning")
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        assert "--failure-threshold" in cmd.command
        idx = cmd.command.index("--failure-threshold")
        assert cmd.command[idx + 1] == "warning"

    def test_command_default_ignored_rules(self, basic_standard_image_target):
        """Test that default ignored rules are applied when none are specified."""
        cmd = HadolintCommand.from_image_target(basic_standard_image_target)
        ignore_indices = [i for i, v in enumerate(cmd.command) if v == "--ignore"]
        assert len(ignore_indices) == len(DEFAULT_IGNORED_RULES)
        ignored_values = [cmd.command[i + 1] for i in ignore_indices]
        assert ignored_values == DEFAULT_IGNORED_RULES

    def test_command_with_ignored_rules(self, basic_standard_image_target):
        """Test that user-provided ignored rules replace the defaults."""
        options = HadolintOptions(ignored=["DL3008", "DL3009"])
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        ignore_indices = [i for i, v in enumerate(cmd.command) if v == "--ignore"]
        assert len(ignore_indices) == 2
        assert cmd.command[ignore_indices[0] + 1] == "DL3008"
        assert cmd.command[ignore_indices[1] + 1] == "DL3009"

    def test_command_with_empty_ignored_rules(self, basic_standard_image_target):
        """Test that explicitly setting ignored to [] clears the defaults."""
        options = HadolintOptions(ignored=[])
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        ignore_indices = [i for i, v in enumerate(cmd.command) if v == "--ignore"]
        assert len(ignore_indices) == 0

    def test_command_with_no_fail(self, basic_standard_image_target):
        """Test that --no-fail is included when set."""
        options = HadolintOptions(noFail=True)
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        assert "--no-fail" in cmd.command

    def test_command_no_fail_false_omitted(self, basic_standard_image_target):
        """Test that --no-fail is NOT included when explicitly False."""
        options = HadolintOptions(noFail=False)
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        assert "--no-fail" not in cmd.command

    def test_command_with_strict_labels(self, basic_standard_image_target):
        """Test that --strict-labels is included when set."""
        options = HadolintOptions(strictLabels=True)
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        assert "--strict-labels" in cmd.command

    def test_command_with_disable_ignore_pragma(self, basic_standard_image_target):
        """Test that --disable-ignore-pragma is included when set."""
        options = HadolintOptions(disableIgnorePragma=True)
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        assert "--disable-ignore-pragma" in cmd.command

    def test_command_with_trusted_registries(self, basic_standard_image_target):
        """Test that --trusted-registry is repeated for each registry."""
        options = HadolintOptions(trustedRegistries=["docker.io", "ghcr.io"])
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        reg_indices = [i for i, v in enumerate(cmd.command) if v == "--trusted-registry"]
        assert len(reg_indices) == 2
        assert cmd.command[reg_indices[0] + 1] == "docker.io"
        assert cmd.command[reg_indices[1] + 1] == "ghcr.io"

    def test_command_with_label_schema(self, basic_standard_image_target):
        """Test that --require-label is repeated for each label."""
        options = HadolintOptions(labelSchema={"maintainer": "text", "version": "semver"})
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        label_indices = [i for i, v in enumerate(cmd.command) if v == "--require-label"]
        assert len(label_indices) == 2
        label_values = [cmd.command[i + 1] for i in label_indices]
        assert "maintainer:text" in label_values
        assert "version:semver" in label_values

    def test_command_with_override(self, basic_standard_image_target):
        """Test that override rules are mapped to the correct flags."""
        options = HadolintOptions(override={"error": ["DL3001"], "warning": ["DL3002", "DL3003"], "info": ["DL3004"]})
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=options)
        error_indices = [i for i, v in enumerate(cmd.command) if v == "--error"]
        assert len(error_indices) == 1
        assert cmd.command[error_indices[0] + 1] == "DL3001"

        warning_indices = [i for i, v in enumerate(cmd.command) if v == "--warning"]
        assert len(warning_indices) == 2

        info_indices = [i for i, v in enumerate(cmd.command) if v == "--info"]
        assert len(info_indices) == 1

    def test_command_with_options_from_variant(self, basic_standard_image_target):
        """Test that options from the image variant are loaded and merged with override."""
        override = HadolintOptions(failureThreshold="warning")
        cmd = HadolintCommand.from_image_target(basic_standard_image_target, options_override=override)
        idx = cmd.command.index("--failure-threshold")
        assert cmd.command[idx + 1] == "warning"
