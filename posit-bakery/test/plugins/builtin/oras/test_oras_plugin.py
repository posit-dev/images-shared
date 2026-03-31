"""Tests for the OrasPlugin."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.image.image_target import ImageTarget, ImageTargetContext, ImageTargetSettings, StringableList
from posit_bakery.plugins.builtin.oras import OrasPlugin
from posit_bakery.plugins.builtin.oras.oras import OrasMergeWorkflowResult
from posit_bakery.plugins.protocol import BakeryToolPlugin

pytestmark = [pytest.mark.unit]


@pytest.fixture
def plugin():
    return OrasPlugin()


@pytest.fixture
def mock_target_with_sources():
    """Create a mock ImageTarget with merge sources."""
    mock_target = MagicMock(spec=ImageTarget)
    mock_target.image_name = "test-image"
    mock_target.uid = "test-image-1-0-0"
    mock_target.temp_registry = "ghcr.io/posit-dev"
    mock_target.context = MagicMock(spec=ImageTargetContext)
    mock_target.context.base_path = Path("/project")
    mock_target.settings = MagicMock(spec=ImageTargetSettings)
    mock_target.settings.temp_registry = "ghcr.io/posit-dev"
    mock_target.get_merge_sources.return_value = [
        "ghcr.io/posit-dev/test/tmp@sha256:amd64digest",
        "ghcr.io/posit-dev/test/tmp@sha256:arm64digest",
    ]
    mock_target.labels = {"org.opencontainers.image.title": "Test Image"}

    mock_tag = MagicMock()
    mock_tag.destination = "ghcr.io/posit-dev/test-image"
    mock_tag.suffix = "1.0.0"
    mock_tag.__str__ = lambda self: "ghcr.io/posit-dev/test-image:1.0.0"
    mock_target.tags = StringableList([mock_tag])

    return mock_target


@pytest.fixture
def mock_target_without_sources():
    """Create a mock ImageTarget without merge sources."""
    mock_target = MagicMock(spec=ImageTarget)
    mock_target.image_name = "no-sources"
    mock_target.uid = "no-sources-1-0-0"
    mock_target.get_merge_sources.return_value = []
    return mock_target


class TestOrasPluginProtocol:
    def test_implements_protocol(self, plugin):
        assert isinstance(plugin, BakeryToolPlugin)

    def test_name(self, plugin):
        assert plugin.name == "oras"

    def test_description(self, plugin):
        assert plugin.description == "Merge multi-platform images using ORAS"


class TestOrasPluginExecute:
    def test_execute_success(self, plugin, mock_target_with_sources):
        with (
            patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            results = plugin.execute(
                Path("/project"),
                [mock_target_with_sources],
            )

        assert len(results) == 1
        assert results[0].exit_code == 0
        assert results[0].tool_name == "oras"
        assert results[0].target is mock_target_with_sources
        assert results[0].artifacts["workflow_result"].success is True

    def test_execute_skips_targets_without_sources(self, plugin, mock_target_without_sources):
        results = plugin.execute(
            Path("/project"),
            [mock_target_without_sources],
        )

        assert len(results) == 0

    def test_execute_missing_temp_registry(self, plugin, mock_target_with_sources):
        mock_target_with_sources.settings.temp_registry = None

        results = plugin.execute(
            Path("/project"),
            [mock_target_with_sources],
        )

        assert len(results) == 1
        assert results[0].exit_code == 1
        assert "temp_registry" in results[0].stderr

    def test_execute_workflow_failure(self, plugin, mock_target_with_sources):
        with (
            patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout=b"", stderr=b"create failed"
            )
            results = plugin.execute(
                Path("/project"),
                [mock_target_with_sources],
            )

        assert len(results) == 1
        assert results[0].exit_code == 1
        assert results[0].artifacts["workflow_result"].success is False

    def test_execute_dry_run(self, plugin, mock_target_with_sources):
        with (
            patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            results = plugin.execute(
                Path("/project"),
                [mock_target_with_sources],
                dry_run=True,
            )

        mock_run.assert_not_called()
        assert len(results) == 1
        assert results[0].exit_code == 0
        assert results[0].artifacts["workflow_result"].success is True

    def test_execute_mixed_targets(self, plugin, mock_target_with_sources, mock_target_without_sources):
        with (
            patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            results = plugin.execute(
                Path("/project"),
                [mock_target_with_sources, mock_target_without_sources],
            )

        # Only the target with sources should produce a result
        assert len(results) == 1
        assert results[0].target is mock_target_with_sources
