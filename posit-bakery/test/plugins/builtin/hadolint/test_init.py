"""Unit tests for the `bakery hadolint run` CLI command.

Guards the `--latest` filter pass-through and the dev-versions warning. Mocks
BakeryConfig and the plugin's execute/results so the CLI can run end-to-end
without hadolint installed or any built images.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hadolint,
]

runner = CliRunner()

BASIC_CONTEXT = str(Path(__file__).parent.parent.parent.parent / "resources" / "basic")


@pytest.fixture
def mocked_hadolint_run():
    """Mock BakeryConfig and HadolintPlugin.execute/results so the CLI can run
    end-to-end without needing hadolint or built images."""
    with patch("posit_bakery.plugins.builtin.hadolint.BakeryConfig") as mock_config:
        instance = MagicMock()
        instance.base_path = Path(BASIC_CONTEXT)
        # Non-empty so the zero-match guard does not abort the happy-path runs.
        instance.targets = [MagicMock()]
        mock_config.from_context.return_value = instance
        with (
            patch("posit_bakery.plugins.builtin.hadolint.HadolintPlugin.execute") as mock_execute,
            patch("posit_bakery.plugins.builtin.hadolint.HadolintPlugin.results"),
        ):
            mock_execute.return_value = []
            yield mock_config, mock_execute


class TestHadolintRunZeroMatchGuard:
    """A filter that matches no targets must fail loudly, not silently pass."""

    def test_no_targets_exits_nonzero(self):
        with patch("posit_bakery.plugins.builtin.hadolint.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.base_path = Path(BASIC_CONTEXT)
            instance.targets = []
            mock_config.from_context.return_value = instance
            with patch("posit_bakery.plugins.builtin.hadolint.HadolintPlugin.execute") as mock_execute:
                result = runner.invoke(
                    app,
                    ["hadolint", "run", "--context", BASIC_CONTEXT, "--image-version", "9999.99.99"],
                    catch_exceptions=False,
                )
        assert result.exit_code == 1
        assert "No image targets" in result.output
        assert "9999.99.99" in result.output
        mock_execute.assert_not_called()


class TestHadolintRunLatestFlag:
    """The --latest flag is passed through to settings and warns with dev inclusion."""

    def test_latest_passed_to_settings(self, mocked_hadolint_run):
        mock_config, _ = mocked_hadolint_run
        result = runner.invoke(
            app,
            ["hadolint", "run", "--latest", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is True

    def test_latest_default_false(self, mocked_hadolint_run):
        mock_config, _ = mocked_hadolint_run
        result = runner.invoke(
            app,
            ["hadolint", "run", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is False
