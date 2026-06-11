"""The consolidated imagetools plugin registers the publish / oras merge / soci convert command
groups, and the merge-phase path runs end-to-end in dry-run."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
import typer

from posit_bakery.image.image_target import ImageTarget, ImageTargetContext, ImageTargetSettings, StringableList
from posit_bakery.plugins.builtin.imagetools import ImageToolsPlugin
from posit_bakery.plugins.builtin.imagetools.publish import MERGE_PHASES
from posit_bakery.plugins.protocol import BakeryToolPlugin

pytestmark = [pytest.mark.unit]


@pytest.fixture
def plugin():
    return ImageToolsPlugin()


@pytest.fixture
def mock_target_with_sources():
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


class TestProtocol:
    def test_implements_protocol(self, plugin):
        assert isinstance(plugin, BakeryToolPlugin)

    def test_name(self, plugin):
        assert plugin.name == "imagetools"


class TestRegisterCli:
    def test_registers_publish_oras_and_soci_groups(self, plugin):
        app = typer.Typer()
        plugin.register_cli(app)
        group_names = {g.name for g in app.registered_groups}
        assert {"imagetools", "oras", "soci"} <= group_names


class TestMergePathDryRun:
    def test_dry_run_merges_end_to_end(self, plugin, mock_target_with_sources):
        # Through the real pipeline + executor; dry-run short-circuits each command before any
        # subprocess, so no tools are required and only the merge phases run.
        results = plugin.execute(Path("/project"), [mock_target_with_sources], phases=MERGE_PHASES, dry_run=True)
        assert len(results) == 1
        assert results[0].exit_code == 0
        assert results[0].target is mock_target_with_sources
