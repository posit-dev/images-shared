"""Tests for --dev-stream deprecation coalesce on commands not covered by test_dev_spec.py.

Verifies that --dev-stream is accepted as a hidden deprecated alias for --dev-channel
on ci merge, ci readme, clean cache-registry, clean temp-registry, get tags, and
run dgoss, and that --dev-channel takes precedence when both flags are provided.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum

runner = CliRunner()
BASIC_CONTEXT = str(Path(__file__).parent.parent / "resources" / "basic")


def _channel_from_settings(mock):
    """Extract dev_channel from the BakerySettings passed to from_context."""
    args, kwargs = mock.from_context.call_args
    settings = kwargs.get("settings", args[1] if len(args) > 1 else None)
    return settings.dev_channel


class TestCiMergeDevStreamDeprecation:
    @pytest.fixture
    def mock_merge(self, tmp_path):
        metadata_file = tmp_path / "meta.json"
        metadata_file.write_text("{}")
        with patch("posit_bakery.cli.ci.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.load_build_metadata_from_file.return_value = []
            instance.targets = []
            mock_config.from_context.return_value = instance
            with patch("posit_bakery.plugins.registry.get_plugin") as mock_plugin:
                mock_oras = MagicMock()
                mock_oras.execute.return_value = []
                mock_plugin.return_value = mock_oras
                yield mock_config, str(metadata_file)

    def test_dev_stream_coalesces(self, mock_merge):
        mock, meta = mock_merge
        result = runner.invoke(
            app,
            ["ci", "merge", meta, "--context", BASIC_CONTEXT, "--dev-stream", "daily"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock) == ReleaseChannelEnum.DAILY

    def test_dev_channel_wins(self, mock_merge):
        mock, meta = mock_merge
        result = runner.invoke(
            app,
            ["ci", "merge", meta, "--context", BASIC_CONTEXT, "--dev-stream", "daily", "--dev-channel", "preview"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock) == ReleaseChannelEnum.PREVIEW


class TestCiReadmeDevStreamDeprecation:
    @pytest.fixture
    def mock_readme(self):
        with patch("posit_bakery.cli.ci.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.targets = []
            mock_config.from_context.return_value = instance
            with patch("posit_bakery.cli.ci.push_readmes", return_value=0):
                yield mock_config

    def test_dev_stream_coalesces(self, mock_readme):
        result = runner.invoke(
            app,
            ["ci", "readme", "--context", BASIC_CONTEXT, "--dev-stream", "daily"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_readme) == ReleaseChannelEnum.DAILY

    def test_dev_channel_wins(self, mock_readme):
        result = runner.invoke(
            app,
            ["ci", "readme", "--context", BASIC_CONTEXT, "--dev-stream", "daily", "--dev-channel", "preview"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_readme) == ReleaseChannelEnum.PREVIEW


class TestCleanCacheRegistryDevStreamDeprecation:
    @pytest.fixture
    def mock_clean(self):
        with patch("posit_bakery.cli.clean.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.clean_caches.return_value = []
            mock_config.from_context.return_value = instance
            yield mock_config

    def test_dev_stream_coalesces(self, mock_clean):
        result = runner.invoke(
            app,
            ["clean", "cache-registry", "ghcr.io/test", "--context", BASIC_CONTEXT, "--dev-stream", "daily"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_clean) == ReleaseChannelEnum.DAILY

    def test_dev_channel_wins(self, mock_clean):
        result = runner.invoke(
            app,
            [
                "clean",
                "cache-registry",
                "ghcr.io/test",
                "--context",
                BASIC_CONTEXT,
                "--dev-stream",
                "daily",
                "--dev-channel",
                "preview",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_clean) == ReleaseChannelEnum.PREVIEW


class TestCleanTempRegistryDevStreamDeprecation:
    @pytest.fixture
    def mock_clean(self):
        with patch("posit_bakery.cli.clean.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.clean_temporary.return_value = []
            mock_config.from_context.return_value = instance
            yield mock_config

    def test_dev_stream_coalesces(self, mock_clean):
        result = runner.invoke(
            app,
            ["clean", "temp-registry", "ghcr.io/test", "--context", BASIC_CONTEXT, "--dev-stream", "daily"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_clean) == ReleaseChannelEnum.DAILY

    def test_dev_channel_wins(self, mock_clean):
        result = runner.invoke(
            app,
            [
                "clean",
                "temp-registry",
                "ghcr.io/test",
                "--context",
                BASIC_CONTEXT,
                "--dev-stream",
                "daily",
                "--dev-channel",
                "preview",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_clean) == ReleaseChannelEnum.PREVIEW


class TestGetTagsDevStreamDeprecation:
    @pytest.fixture
    def mock_get(self):
        with patch("posit_bakery.cli.get.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.targets = []
            mock_config.from_context.return_value = instance
            yield mock_config

    def test_dev_stream_coalesces(self, mock_get):
        result = runner.invoke(
            app,
            ["get", "tags", "--context", BASIC_CONTEXT, "--dev-stream", "daily"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_get) == ReleaseChannelEnum.DAILY

    def test_dev_channel_wins(self, mock_get):
        result = runner.invoke(
            app,
            ["get", "tags", "--context", BASIC_CONTEXT, "--dev-stream", "daily", "--dev-channel", "preview"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_get) == ReleaseChannelEnum.PREVIEW


class TestRunDgossDevStreamDeprecation:
    @pytest.fixture
    def mock_run(self):
        with patch("posit_bakery.cli.run.BakeryConfig") as mock_config:
            instance = MagicMock()
            instance.base_path = Path(BASIC_CONTEXT)
            instance.targets = []
            mock_config.from_context.return_value = instance
            with patch("posit_bakery.cli.run.get_plugin") as mock_plugin:
                mock_dgoss = MagicMock()
                mock_dgoss.execute.return_value = []
                mock_plugin.return_value = mock_dgoss
                yield mock_config

    def test_dev_stream_coalesces(self, mock_run):
        result = runner.invoke(
            app,
            ["run", "dgoss", "--context", BASIC_CONTEXT, "--dev-stream", "daily"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_run) == ReleaseChannelEnum.DAILY

    def test_dev_channel_wins(self, mock_run):
        result = runner.invoke(
            app,
            ["run", "dgoss", "--context", BASIC_CONTEXT, "--dev-stream", "daily", "--dev-channel", "preview"],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        assert _channel_from_settings(mock_run) == ReleaseChannelEnum.PREVIEW
