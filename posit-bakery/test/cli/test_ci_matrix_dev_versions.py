"""Tests for bakery ci matrix with images that have both matrix: and devVersions:.

Covers two regression scenarios where dev versions from a matrix image were
silently dropped from the output:

  Issue 1: --matrix-versions only --dev-versions only  → returned []
  Issue 2: --matrix-versions include --dev-versions only → excluded matrix images with dev versions
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.config.image.posit_product.const import ReleaseChannelEnum
from posit_bakery.const import DevVersionInclusionEnum

runner = CliRunner()
BASIC_CONTEXT = str(Path(__file__).parent.parent / "resources" / "basic")


def _make_version(name: str, *, is_dev: bool, channel: ReleaseChannelEnum | None = None):
    """Return a minimal MagicMock ImageVersion with working matches_dev_filter."""
    ver = MagicMock()
    ver.name = name
    ver.isDevelopmentVersion = is_dev
    ver.metadata = {"release_channel": channel} if channel else {}
    ver.supported_platforms = ["linux/amd64"]

    def matches_dev_filter(dev_versions, dev_channel=None):
        if is_dev and dev_versions == DevVersionInclusionEnum.EXCLUDE:
            return False, "excluded by --dev-versions exclude"
        if not is_dev and dev_versions == DevVersionInclusionEnum.ONLY:
            return False, "not a development version (excluded by --dev-versions only)"
        if dev_channel is not None and is_dev:
            if channel != dev_channel:
                return False, f"channel mismatch"
        return True, None

    ver.matches_dev_filter = matches_dev_filter
    return ver


def _make_matrix_image(name: str, dev_versions: list, prod_versions: list):
    """Return a mock Image with both a matrix and pre-loaded dev versions."""
    img = MagicMock()
    img.name = name

    matrix = MagicMock()
    matrix.to_image_versions.return_value = prod_versions
    img.matrix = matrix

    # img.versions simulates the state *after* load_dev_versions() has been called.
    # In practice bakery loads dev versions into image.versions; prod matrix versions
    # come from img.matrix.to_image_versions() at filter time.
    img.versions = dev_versions

    return img


@pytest.fixture
def mock_config_with_matrix_dev_image():
    """Patch BakeryConfig to return a single matrix image with a dev version loaded."""
    dev_ver = _make_version("2026.99.0-dev+1", is_dev=True, channel=ReleaseChannelEnum.DAILY)
    prod_ver1 = _make_version("2026.1.0", is_dev=False)
    prod_ver2 = _make_version("2026.2.0", is_dev=False)
    img = _make_matrix_image("positron-session", [dev_ver], [prod_ver1, prod_ver2])

    with patch("posit_bakery.cli.ci.BakeryConfig") as mock:
        instance = MagicMock()
        instance.model.images = [img]
        mock.from_context.return_value = instance
        yield mock, dev_ver, prod_ver1, prod_ver2


class TestCiMatrixDevVersionsOnly:
    """Issue 1: --matrix-versions only --dev-versions only returned []."""

    def test_dev_version_included(self, mock_config_with_matrix_dev_image):
        _, dev_ver, _, _ = mock_config_with_matrix_dev_image
        result = runner.invoke(
            app,
            [
                "ci",
                "matrix",
                "--context",
                BASIC_CONTEXT,
                "--matrix-versions",
                "only",
                "--dev-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout.strip())
        assert len(data) == 1
        assert data[0]["version"] == dev_ver.name
        assert data[0]["dev"] is True

    def test_prod_versions_excluded(self, mock_config_with_matrix_dev_image):
        _, _, prod_ver1, prod_ver2 = mock_config_with_matrix_dev_image
        result = runner.invoke(
            app,
            [
                "ci",
                "matrix",
                "--context",
                BASIC_CONTEXT,
                "--matrix-versions",
                "only",
                "--dev-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout.strip())
        versions_in_output = {e["version"] for e in data}
        assert prod_ver1.name not in versions_in_output
        assert prod_ver2.name not in versions_in_output


class TestCiMatrixDevVersionsInclude:
    """Issue 2: --matrix-versions include --dev-versions only omitted matrix images' dev versions."""

    def test_dev_version_included(self, mock_config_with_matrix_dev_image):
        _, dev_ver, _, _ = mock_config_with_matrix_dev_image
        result = runner.invoke(
            app,
            [
                "ci",
                "matrix",
                "--context",
                BASIC_CONTEXT,
                "--matrix-versions",
                "include",
                "--dev-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout.strip())
        dev_entries = [e for e in data if e["dev"]]
        assert len(dev_entries) == 1
        assert dev_entries[0]["version"] == dev_ver.name

    def test_prod_versions_excluded(self, mock_config_with_matrix_dev_image):
        """With --dev-versions only, production matrix versions are filtered out."""
        _, _, prod_ver1, prod_ver2 = mock_config_with_matrix_dev_image
        result = runner.invoke(
            app,
            [
                "ci",
                "matrix",
                "--context",
                BASIC_CONTEXT,
                "--matrix-versions",
                "include",
                "--dev-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout.strip())
        versions_in_output = {e["version"] for e in data}
        assert prod_ver1.name not in versions_in_output
        assert prod_ver2.name not in versions_in_output


@pytest.fixture
def mock_config_with_two_channel_dev_image():
    """Patch BakeryConfig to return one non-matrix image carrying both a
    daily and a preview dev version (the workbench/session-init shape)."""
    daily = _make_version("2026.99.0+237", is_dev=True, channel=ReleaseChannelEnum.DAILY)
    preview = _make_version("2026.99.0+240", is_dev=True, channel=ReleaseChannelEnum.PREVIEW)
    img = MagicMock()
    img.name = "workbench"
    img.matrix = None
    img.versions = [daily, preview]

    with patch("posit_bakery.cli.ci.BakeryConfig") as mock:
        instance = MagicMock()
        instance.model.images = [img]
        mock.from_context.return_value = instance
        yield mock, daily, preview


class TestCiMatrixDevSpecChannelFilter:
    """A --dev-spec carrying a channel filters the matrix to that channel even
    when --dev-channel is omitted. The shared workflow folds the channel into
    the dev-spec and drops --dev-channel, so the matrix must honor it."""

    def test_filters_to_dev_spec_channel(self, mock_config_with_two_channel_dev_image):
        _, daily, preview = mock_config_with_two_channel_dev_image
        result = runner.invoke(
            app,
            [
                "ci",
                "matrix",
                "--context",
                BASIC_CONTEXT,
                "--dev-versions",
                "only",
                "--dev-spec",
                '{"version": "2026.99.0+240", "channel": "preview"}',
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout.strip())
        versions = {e["version"] for e in data}
        assert preview.name in versions
        assert daily.name not in versions

    def test_branch_only_dev_spec_does_not_filter(self, mock_config_with_two_channel_dev_image):
        """A branch-only dev-spec carries no channel, so all channels stay in the matrix."""
        _, daily, preview = mock_config_with_two_channel_dev_image
        result = runner.invoke(
            app,
            [
                "ci",
                "matrix",
                "--context",
                BASIC_CONTEXT,
                "--dev-versions",
                "only",
                "--dev-spec",
                '{"release_branch": "2026.06"}',
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        data = json.loads(result.stdout.strip())
        versions = {e["version"] for e in data}
        assert preview.name in versions
        assert daily.name in versions
