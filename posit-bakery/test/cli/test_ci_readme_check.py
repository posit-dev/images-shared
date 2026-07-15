"""Tests for the `bakery ci readme --check` flag.

--check validates README length against Docker Hub's limit without
authenticating or pushing, so it can run in fork PR CI where Docker Hub
credentials are not available (see .github/workflows/bakery-build-pr.yml).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [pytest.mark.unit]

runner = CliRunner()
BASIC_CONTEXT = str(Path(__file__).parent.parent / "resources" / "basic")
_ENV = {"TERM": "dumb", "NO_COLOR": "true", "COLUMNS": "200"}


@pytest.fixture
def mock_config():
    with patch("posit_bakery.cli.ci.BakeryConfig") as mock_config_cls:
        instance = MagicMock()
        instance.targets = []
        mock_config_cls.from_context.return_value = instance
        yield mock_config_cls


class TestReadmeCheckFlag:
    def test_passes_with_no_violations(self, mock_config):
        with patch("posit_bakery.cli.ci.find_oversized_readmes", return_value=[]) as mock_find:
            with patch("posit_bakery.cli.ci.push_readmes") as mock_push:
                result = runner.invoke(
                    app,
                    ["ci", "readme", "--check", "--context", BASIC_CONTEXT],
                    catch_exceptions=False,
                    env=_ENV,
                )

        assert result.exit_code == 0, result.stdout + result.stderr
        mock_find.assert_called_once_with(mock_config.from_context.return_value.targets)
        mock_push.assert_not_called()

    def test_fails_with_violations(self, mock_config):
        violation = (
            "/repo/workbench/README.md is 25,069 bytes, exceeding Docker Hub's "
            "25,000-byte README limit by 69 bytes"
        )
        with patch("posit_bakery.cli.ci.find_oversized_readmes", return_value=[violation]):
            with patch("posit_bakery.cli.ci.push_readmes") as mock_push:
                result = runner.invoke(
                    app,
                    ["ci", "readme", "--check", "--context", BASIC_CONTEXT],
                    catch_exceptions=False,
                    env=_ENV,
                )

        assert result.exit_code == 1
        assert violation in result.stderr
        mock_push.assert_not_called()

    def test_reports_all_violations(self, mock_config):
        violations = ["README A is oversized", "README B is oversized"]
        with patch("posit_bakery.cli.ci.find_oversized_readmes", return_value=violations):
            with patch("posit_bakery.cli.ci.push_readmes"):
                result = runner.invoke(
                    app,
                    ["ci", "readme", "--check", "--context", BASIC_CONTEXT],
                    catch_exceptions=False,
                    env=_ENV,
                )

        assert result.exit_code == 1
        assert "README A is oversized" in result.stderr
        assert "README B is oversized" in result.stderr

    def test_without_check_does_not_call_find(self, mock_config):
        with patch("posit_bakery.cli.ci.find_oversized_readmes") as mock_find:
            with patch("posit_bakery.cli.ci.push_readmes", return_value=0) as mock_push:
                result = runner.invoke(
                    app,
                    ["ci", "readme", "--context", BASIC_CONTEXT],
                    catch_exceptions=False,
                    env=_ENV,
                )

        assert result.exit_code == 0
        mock_find.assert_not_called()
        mock_push.assert_called_once()

    def test_help_lists_check_flag(self):
        result = runner.invoke(app, ["ci", "readme", "--help"], env=_ENV)
        assert result.exit_code == 0
        assert "--check" in result.stdout
