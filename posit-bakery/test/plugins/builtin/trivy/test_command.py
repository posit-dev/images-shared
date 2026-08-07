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
        command_str = " ".join(cmd.command)
        assert "image" in cmd.command
        assert "--format" in cmd.command
        assert "sarif" in cmd.command
        assert "--output" in cmd.command
        assert str(cmd.results_file) in command_str
        assert "--quiet" in cmd.command

    def test_command_never_sets_exit_code_flag(self, basic_standard_image_target):
        """Trivy's own --exit-code flag must never be passed (see Global Constraints)."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
        )
        assert "--exit-code" not in cmd.command

    def test_command_with_cli_severity_and_timeout(self, basic_standard_image_target):
        """Test that CLI severity/timeout options are passed through."""
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            severity="HIGH,CRITICAL",
            timeout="10m",
        )
        assert "--severity" in cmd.command
        assert "HIGH,CRITICAL" in cmd.command
        assert "--timeout" in cmd.command
        assert "10m" in cmd.command

    def test_command_disabled_scanners_computes_complement(self, basic_standard_image_target):
        """--disabled-scanners is translated into the enabled complement passed as --scanners."""
        from posit_bakery.plugins.builtin.trivy.command import TRIVY_ALL_SCANNERS

        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            disabled_scanners="secret,license",
        )
        idx = cmd.command.index("--scanners")
        enabled = cmd.command[idx + 1].split(",")
        assert "secret" not in enabled
        assert "license" not in enabled
        for scanner in TRIVY_ALL_SCANNERS:
            if scanner not in ("secret", "license"):
                assert scanner in enabled

    def test_command_with_tool_options(self, basic_standard_image_target):
        """Test that ToolOptions fields are included in the command when no CLI value is given."""
        from posit_bakery.plugins.builtin.trivy.options import TrivyOptions

        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            tool_options=TrivyOptions(severity=["HIGH", "CRITICAL"], timeout="5m"),
        )
        command_str = " ".join(cmd.command)
        assert "--severity" in command_str
        assert "HIGH,CRITICAL" in command_str
        assert "--timeout" in command_str
        assert "5m" in command_str

    def test_cli_severity_wins_over_tool_options(self, basic_standard_image_target):
        """An explicit CLI value takes precedence over the bakery.yaml TrivyOptions value."""
        from posit_bakery.plugins.builtin.trivy.options import TrivyOptions

        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            severity="LOW",
            tool_options=TrivyOptions(severity=["HIGH", "CRITICAL"]),
        )
        idx = cmd.command.index("--severity")
        assert cmd.command[idx + 1] == "LOW"

    def test_command_with_native_config(self, basic_standard_image_target, tmp_path):
        """Test that an explicit --trivy-config path is passed through via --config."""
        config_path = tmp_path / "trivy.yaml"
        config_path.write_text("severity:\n  - CRITICAL\n")
        results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
        cmd = TrivyCommand.from_image_target(
            image_target=basic_standard_image_target,
            results_dir=results_dir,
            trivy_config=config_path,
        )
        assert "--config" in cmd.command
        assert str(config_path) in cmd.command

    def test_discover_trivy_config_finds_conventional_path(self, basic_standard_image_target, tmp_path):
        """discover_trivy_config finds <base_path>/<image_name>/trivy.yaml when present."""
        from posit_bakery.plugins.builtin.trivy.command import discover_trivy_config

        image_dir = basic_standard_image_target.context.base_path / basic_standard_image_target.image_name
        image_dir.mkdir(parents=True, exist_ok=True)
        config_path = image_dir / "trivy.yaml"
        config_path.write_text("severity:\n  - CRITICAL\n")

        found = discover_trivy_config(basic_standard_image_target)
        assert found == config_path

        config_path.unlink()

    def test_discover_trivy_config_returns_none_when_absent(self, basic_standard_image_target):
        from posit_bakery.plugins.builtin.trivy.command import discover_trivy_config

        image_dir = basic_standard_image_target.context.base_path / basic_standard_image_target.image_name
        conventional = image_dir / "trivy.yaml"
        if conventional.exists():
            pytest.skip("fixture project unexpectedly has a trivy.yaml already")

        assert discover_trivy_config(basic_standard_image_target) is None

    def test_validate_no_trivy_bin(self, basic_standard_image_target):
        """Test that validation fails if trivy binary cannot be found."""
        with patch("posit_bakery.plugins.builtin.trivy.command.find_trivy_bin") as mock:
            mock.return_value = None
            with pytest.raises(ValidationError, match="trivy binary path must be specified"):
                results_dir = basic_standard_image_target.context.base_path / "results" / "trivy"
                TrivyCommand.from_image_target(
                    image_target=basic_standard_image_target,
                    results_dir=results_dir,
                )
