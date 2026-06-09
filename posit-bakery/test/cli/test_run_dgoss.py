"""Unit tests for the deprecated `bakery run dgoss` CLI command.

Guards the same platform normalization behavior as `bakery dgoss run`. See
`test/plugins/builtin/dgoss/test_init.py` for the equivalent coverage on the
non-deprecated command path.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

runner = CliRunner()

BASIC_CONTEXT = str(Path(__file__).parent.parent / "resources" / "basic")


@pytest.fixture
def mocked_bakery_run_dgoss():
    """Mock BakeryConfig and the DGoss plugin's execute method so the CLI can
    run end-to-end without needing a Docker daemon or built images."""
    with patch("posit_bakery.cli.run.BakeryConfig") as mock_config:
        instance = MagicMock()
        instance.base_path = Path(BASIC_CONTEXT)
        instance.targets = []
        mock_config.from_context.return_value = instance
        with patch("posit_bakery.cli.run.get_plugin") as mock_get_plugin:
            mock_plugin = MagicMock()
            mock_plugin.execute.return_value = []
            mock_get_plugin.return_value = mock_plugin
            yield mock_config, mock_plugin


class TestRunDgossPlatformNormalization:
    """Regression coverage: `--image-platform linux/amd64` must not become
    `linux/linux/amd64`."""

    @pytest.mark.parametrize(
        "given,expected",
        [
            ("amd64", "linux/amd64"),
            ("arm64", "linux/arm64"),
            ("linux/amd64", "linux/amd64"),
            ("linux/arm64", "linux/arm64"),
        ],
    )
    def test_normalizes_platform(self, mocked_bakery_run_dgoss, given, expected):
        mock_config, mock_plugin = mocked_bakery_run_dgoss
        result = runner.invoke(
            app,
            ["run", "dgoss", "--context", BASIC_CONTEXT, "--image-platform", given],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.filter.image_platform == [expected]
        assert mock_plugin.execute.call_args[1]["platform"] == expected


class TestRunDgossLatestFlag:
    """The --latest flag is passed through to settings and warns with dev inclusion."""

    def test_latest_passed_to_settings(self, mocked_bakery_run_dgoss):
        mock_config, _ = mocked_bakery_run_dgoss
        result = runner.invoke(
            app,
            ["run", "dgoss", "--latest", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is True

    def test_latest_default_false(self, mocked_bakery_run_dgoss):
        mock_config, _ = mocked_bakery_run_dgoss
        result = runner.invoke(
            app,
            ["run", "dgoss", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.stdout
        settings = mock_config.from_context.call_args[0][1]
        assert settings.latest is False


def test_run_accepts_jobs_flag(tmp_path):
    """`dgoss run --jobs N` forwards jobs into the plugin's execute()."""
    from posit_bakery.plugins.builtin.dgoss import DGossPlugin

    with (
        patch("posit_bakery.plugins.builtin.dgoss.BakeryConfig") as mock_config,
        patch.object(DGossPlugin, "execute", return_value=[]) as execute_spy,
        patch.object(DGossPlugin, "results", return_value=None),
    ):
        instance = MagicMock()
        instance.base_path = tmp_path
        instance.targets = []
        mock_config.from_context.return_value = instance

        result = runner.invoke(
            app,
            ["dgoss", "run", "--context", str(tmp_path), "--jobs", "2"],
            catch_exceptions=False,
        )

        assert result.exit_code == 0, result.output
        assert execute_spy.call_args.kwargs["jobs"] == 2
