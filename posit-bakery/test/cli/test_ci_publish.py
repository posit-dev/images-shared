"""Tests for the `bakery ci publish` orchestrator."""

import subprocess
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [pytest.mark.unit]


def test_publish_help_lists_command():
    runner = CliRunner()
    result = runner.invoke(app, ["ci", "--help"])
    assert result.exit_code == 0
    assert "publish" in result.stdout


def test_publish_command_flags_present():
    runner = CliRunner()
    result = runner.invoke(app, ["ci", "publish", "--help"])
    assert result.exit_code == 0
    assert "--enable-soci" in result.stdout
    assert "--temp-registry" in result.stdout
    assert "--dry-run" in result.stdout
