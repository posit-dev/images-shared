"""Unit tests for the `bakery trivy scan` CLI command.

Guards the `--latest` filter pass-through and the zero-target guard. Mocks
BakeryConfig and the plugin's execute/results so the CLI can run end-to-end
without trivy installed or any built images.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [
    pytest.mark.unit,
    pytest.mark.trivy,
]

runner = CliRunner()

BASIC_CONTEXT = str(Path(__file__).parent.parent.parent.parent / "resources" / "basic")


@pytest.fixture
def mocked_trivy_scan():
    """Mock BakeryConfig and TrivyPlugin.execute/results so the CLI can run
    end-to-end without needing trivy or built images."""
    with patch("posit_bakery.plugins.builtin.trivy.BakeryConfig") as mock_config:
        instance = MagicMock()
        instance.base_path = Path(BASIC_CONTEXT)
        instance.targets = [MagicMock()]
        mock_config.from_context.return_value = instance
        with (
            patch("posit_bakery.plugins.builtin.trivy.TrivyPlugin.execute") as mock_execute,
            patch("posit_bakery.plugins.builtin.trivy.TrivyPlugin.results"),
        ):
            mock_execute.return_value = []
            yield mock_config, mock_execute


class TestTrivyScanZeroMatchGuard:
    """A filter that matches no targets must fail loudly, not silently pass."""

    def test_no_targets_exits_nonzero(self):
        with patch("posit_bakery.plugins.builtin.trivy.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.base_path = Path(BASIC_CONTEXT)
            instance.targets = []
            mock_config.from_context.return_value = instance
            with patch("posit_bakery.plugins.builtin.trivy.TrivyPlugin.execute") as mock_execute:
                result = runner.invoke(
                    app,
                    ["trivy", "scan", "--context", BASIC_CONTEXT, "--image-version", "9999.99.99"],
                    catch_exceptions=False,
                )
        assert result.exit_code == 1
        assert "No image targets" in result.output
        mock_execute.assert_not_called()


class TestTrivyScanLatestFlag:
    """The --latest flag is passed through to settings."""

    def test_latest_passed_to_settings(self, mocked_trivy_scan):
        mock_config, _ = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--latest", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is True

    def test_latest_default_false(self, mocked_trivy_scan):
        mock_config, _ = mocked_trivy_scan
        result = runner.invoke(
            app,
            ["trivy", "scan", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is False


class TestTrivyScanFlagPassthrough:
    def test_severity_and_fail_on_severity_passed_to_execute(self, mocked_trivy_scan):
        _, mock_execute = mocked_trivy_scan
        result = runner.invoke(
            app,
            [
                "trivy",
                "scan",
                "--context",
                BASIC_CONTEXT,
                "--severity",
                "HIGH,CRITICAL",
                "--fail-on-severity",
                "CRITICAL",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        _, kwargs = mock_execute.call_args
        assert kwargs["severity"] == "HIGH,CRITICAL"
        assert kwargs["fail_on_severity"] == "CRITICAL"

    def test_no_authentication_panel(self):
        """Guards the design decision: Trivy has no Authentication help panel."""
        result = runner.invoke(app, ["trivy", "scan", "--help"], catch_exceptions=False)
        assert result.exit_code == 0
        assert "Authentication" not in result.output
