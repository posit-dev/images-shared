"""Tests for the ORAS merge side of the ImageToolsPlugin (merge_execute)."""

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from posit_bakery.image.image_target import ImageTarget, ImageTargetContext, ImageTargetSettings, StringableList
from posit_bakery.plugins.builtin.imagetools import ImageToolsPlugin
from posit_bakery.plugins.builtin.imagetools.oras import OrasMergeWorkflowResult
from posit_bakery.plugins.protocol import BakeryToolPlugin

pytestmark = [pytest.mark.unit]


@pytest.fixture
def plugin():
    return ImageToolsPlugin()


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
    mock_target.push_sort_key = (0,)

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
    mock_target.push_sort_key = (0,)
    return mock_target


class TestImageToolsPluginProtocol:
    def test_implements_protocol(self, plugin):
        assert isinstance(plugin, BakeryToolPlugin)

    def test_name(self, plugin):
        assert plugin.name == "imagetools"

    def test_description(self, plugin):
        assert plugin.description == "Merge and SOCI-convert multi-platform images (ORAS + SOCI)"


class TestImageToolsPluginMergeExecute:
    def test_merge_execute_success(self, plugin, mock_target_with_sources):
        with (
            patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            results = plugin.merge_execute(
                Path("/project"),
                [mock_target_with_sources],
            )

        assert len(results) == 1
        assert results[0].exit_code == 0
        assert results[0].tool_name == "oras"
        assert results[0].target is mock_target_with_sources
        assert results[0].artifacts["workflow_result"].success is True

    def test_merge_execute_skips_targets_without_sources(self, plugin, mock_target_without_sources):
        results = plugin.merge_execute(
            Path("/project"),
            [mock_target_without_sources],
        )

        assert len(results) == 0

    def test_merge_execute_missing_temp_registry(self, plugin, mock_target_with_sources):
        mock_target_with_sources.settings.temp_registry = None

        results = plugin.merge_execute(
            Path("/project"),
            [mock_target_with_sources],
        )

        assert len(results) == 1
        assert results[0].exit_code == 1
        assert "temp_registry" in results[0].stderr

    def test_merge_execute_workflow_failure(self, plugin, mock_target_with_sources):
        with (
            patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=1, stdout=b"", stderr=b"create failed"
            )
            results = plugin.merge_execute(
                Path("/project"),
                [mock_target_with_sources],
            )

        assert len(results) == 1
        assert results[0].exit_code == 1
        assert results[0].artifacts["workflow_result"].success is False

    def test_merge_execute_dry_run(self, plugin, mock_target_with_sources):
        with (
            patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            results = plugin.merge_execute(
                Path("/project"),
                [mock_target_with_sources],
                dry_run=True,
            )

        mock_run.assert_not_called()
        assert len(results) == 1
        assert results[0].exit_code == 0
        assert results[0].artifacts["workflow_result"].success is True

    def test_merge_execute_mixed_targets(self, plugin, mock_target_with_sources, mock_target_without_sources):
        with (
            patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
            patch("subprocess.run") as mock_run,
        ):
            mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
            results = plugin.merge_execute(
                Path("/project"),
                [mock_target_with_sources, mock_target_without_sources],
            )

        # Only the target with sources should produce a result
        assert len(results) == 1
        assert results[0].target is mock_target_with_sources

    def test_merge_execute_processes_targets_in_push_sort_key_order(self, plugin, caplog):
        """Targets are processed in ascending push_sort_key order, regardless of input order."""

        def make_target(name, sort_key):
            t = MagicMock(spec=ImageTarget)
            t.image_name = name
            t.uid = f"{name}-uid"
            t.context = MagicMock(spec=ImageTargetContext)
            t.context.base_path = Path("/project")
            t.settings = MagicMock(spec=ImageTargetSettings)
            t.settings.temp_registry = "ghcr.io/posit-dev"
            t.get_merge_sources.return_value = [f"ghcr.io/posit-dev/{name}/tmp@sha256:digest"]
            t.labels = {}
            mock_tag = MagicMock()
            mock_tag.destination = f"ghcr.io/posit-dev/{name}"
            mock_tag.suffix = "1.0.0"
            mock_tag.__str__ = lambda self: f"ghcr.io/posit-dev/{name}:1.0.0"
            t.tags = StringableList([mock_tag])
            # Override push_sort_key to a controlled tuple so the test is independent of
            # ImageVersion / ImageVariant internals.
            t.push_sort_key = sort_key
            t.__str__ = lambda self: name
            return t

        # Input order is intentionally scrambled.
        targets = [
            make_target("c-second", (1,)),
            make_target("a-first", (0,)),
            make_target("d-last", (3,)),
            make_target("b-third", (2,)),
        ]
        expected_order = ["a-first", "c-second", "b-third", "d-last"]

        call_order = []

        def fake_run(self_workflow, dry_run=False):
            call_order.append(self_workflow.image_target.image_name)
            return OrasMergeWorkflowResult(success=True, destinations=[])

        with (
            patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasMergeWorkflow.run",
                autospec=True,
                side_effect=fake_run,
            ),
            caplog.at_level(logging.INFO, logger="posit_bakery.plugins.builtin.imagetools.imagetools"),
        ):
            plugin.merge_execute(Path("/project"), targets)

        assert call_order == expected_order, f"got {call_order}, want {expected_order}"
        order_log_lines = [r for r in caplog.records if "ORAS merge order:" in r.getMessage()]
        assert len(order_log_lines) == 1, "expected exactly one ORAS merge order log line"
        msg = order_log_lines[0].getMessage()
        assert msg.endswith("a-first, c-second, b-third, d-last"), msg


class TestImageToolsPluginCLI:
    def test_register_cli_adds_command_groups(self, plugin):
        app = typer.Typer()
        plugin.register_cli(app)

        # The canonical `imagetools` group plus the hidden back-compat aliases
        # (`oras`, `soci`) should all be registered.
        group_names = [g.name for g in app.registered_groups]
        assert "imagetools" in group_names
        assert "oras" in group_names
        assert "soci" in group_names
