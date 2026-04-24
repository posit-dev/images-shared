"""Tests for the bakery clean CLI commands.

Verifies that --dev-versions and --matrix-versions flags are accepted
and correctly passed through to BakerySettings for both cache-registry
and temp-registry subcommands.

Tests cover the three flag combinations used by actual workflows:
  - exclude/exclude (production)
  - only/exclude (development)
  - exclude/only (content, session)

The "include" value is only spot-checked to verify the flag is accepted.
Full combinatorial coverage of "include" is omitted because no workflow
builds all version categories at once, so no clean job should either.
Each clean job should match exactly what its sibling build job produces.
"""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum

runner = CliRunner()

BASIC_CONTEXT = str(Path(__file__).parent.parent / "resources" / "basic")


@pytest.fixture
def mock_config():
    """Mock BakeryConfig and clean functions to capture settings without making API calls."""
    with (
        patch("posit_bakery.cli.clean.BakeryConfig") as mock,
        patch("posit_bakery.cli.clean.do_clean_caches", return_value=[]),
        patch("posit_bakery.cli.clean.do_clean_temporary", return_value=[]),
    ):
        instance = MagicMock()
        mock.from_context.return_value = instance
        yield mock


class TestCacheRegistry:
    def test_defaults(self, mock_config):
        result = runner.invoke(
            app,
            ["clean", "cache-registry", "ghcr.io/test", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_config.from_context.call_args[1].get("settings", mock_config.from_context.call_args[0][1])
        assert settings.dev_versions == DevVersionInclusionEnum.EXCLUDE
        assert settings.matrix_versions == MatrixVersionInclusionEnum.EXCLUDE

    def test_dev_versions_only(self, mock_config):
        result = runner.invoke(
            app,
            [
                "clean",
                "cache-registry",
                "ghcr.io/test",
                "--context",
                BASIC_CONTEXT,
                "--dev-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_config.from_context.call_args[1].get("settings", mock_config.from_context.call_args[0][1])
        assert settings.dev_versions == DevVersionInclusionEnum.ONLY

    def test_matrix_versions_only(self, mock_config):
        result = runner.invoke(
            app,
            [
                "clean",
                "cache-registry",
                "ghcr.io/test",
                "--context",
                BASIC_CONTEXT,
                "--matrix-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_config.from_context.call_args[1].get("settings", mock_config.from_context.call_args[0][1])
        assert settings.matrix_versions == MatrixVersionInclusionEnum.ONLY

    def test_dev_and_matrix_combined(self, mock_config):
        result = runner.invoke(
            app,
            [
                "clean",
                "cache-registry",
                "ghcr.io/test",
                "--context",
                BASIC_CONTEXT,
                "--dev-versions",
                "only",
                "--matrix-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_config.from_context.call_args[1].get("settings", mock_config.from_context.call_args[0][1])
        assert settings.dev_versions == DevVersionInclusionEnum.ONLY
        assert settings.matrix_versions == MatrixVersionInclusionEnum.ONLY

    def test_dev_versions_include(self, mock_config):
        result = runner.invoke(
            app,
            [
                "clean",
                "cache-registry",
                "ghcr.io/test",
                "--context",
                BASIC_CONTEXT,
                "--dev-versions",
                "include",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_config.from_context.call_args[1].get("settings", mock_config.from_context.call_args[0][1])
        assert settings.dev_versions == DevVersionInclusionEnum.INCLUDE


class TestTempRegistry:
    def test_defaults(self, mock_config):
        result = runner.invoke(
            app,
            ["clean", "temp-registry", "ghcr.io/test", "--context", BASIC_CONTEXT],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_config.from_context.call_args[1].get("settings", mock_config.from_context.call_args[0][1])
        assert settings.dev_versions == DevVersionInclusionEnum.EXCLUDE
        assert settings.matrix_versions == MatrixVersionInclusionEnum.EXCLUDE

    def test_dev_versions_only(self, mock_config):
        result = runner.invoke(
            app,
            [
                "clean",
                "temp-registry",
                "ghcr.io/test",
                "--context",
                BASIC_CONTEXT,
                "--dev-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_config.from_context.call_args[1].get("settings", mock_config.from_context.call_args[0][1])
        assert settings.dev_versions == DevVersionInclusionEnum.ONLY

    def test_matrix_versions_only(self, mock_config):
        result = runner.invoke(
            app,
            [
                "clean",
                "temp-registry",
                "ghcr.io/test",
                "--context",
                BASIC_CONTEXT,
                "--matrix-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_config.from_context.call_args[1].get("settings", mock_config.from_context.call_args[0][1])
        assert settings.matrix_versions == MatrixVersionInclusionEnum.ONLY

    def test_dev_and_matrix_combined(self, mock_config):
        result = runner.invoke(
            app,
            [
                "clean",
                "temp-registry",
                "ghcr.io/test",
                "--context",
                BASIC_CONTEXT,
                "--dev-versions",
                "only",
                "--matrix-versions",
                "only",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0
        settings = mock_config.from_context.call_args[1].get("settings", mock_config.from_context.call_args[0][1])
        assert settings.dev_versions == DevVersionInclusionEnum.ONLY
        assert settings.matrix_versions == MatrixVersionInclusionEnum.ONLY
