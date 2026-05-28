"""Tests for the `bakery soci convert` CLI command."""

import json
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [pytest.mark.unit]


def test_soci_convert_help_lists_subcommand():
    runner = CliRunner()
    result = runner.invoke(app, ["soci", "--help"])
    assert result.exit_code == 0
    assert "convert" in result.stdout


def test_soci_convert_requires_metadata_file_argument():
    runner = CliRunner()
    result = runner.invoke(app, ["soci", "convert"])
    assert result.exit_code != 0
