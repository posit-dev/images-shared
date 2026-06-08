"""Tests for the `bakery soci convert` CLI command."""

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [pytest.mark.unit]

# Force a wide, unstyled terminal so rich/typer doesn't line-wrap option
# names across rows with embedded ANSI escapes, which defeats substring
# assertions on narrow CI terminals.
_WIDE_TERM_ENV = {"COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"}


def test_soci_convert_help_lists_subcommand():
    runner = CliRunner()
    result = runner.invoke(app, ["soci", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0
    assert "convert" in result.stdout


def test_soci_convert_requires_metadata_file_argument():
    runner = CliRunner()
    result = runner.invoke(app, ["soci", "convert"])
    assert result.exit_code != 0


def test_soci_convert_help_lists_soci_mode_option():
    runner = CliRunner()
    result = runner.invoke(app, ["soci", "convert", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0
    assert "--soci-mode" in result.stdout
    # The legacy boolean flag is gone.
    assert "--standalone" not in result.stdout


def test_soci_convert_rejects_invalid_mode():
    runner = CliRunner()
    result = runner.invoke(app, ["soci", "convert", "meta.json", "--soci-mode", "bogus"])
    assert result.exit_code != 0
