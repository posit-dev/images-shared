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


def test_soci_convert_help_has_no_mode_option():
    runner = CliRunner()
    result = runner.invoke(app, ["soci", "convert", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0
    # Conversion is standalone-only; there is no mode selector.
    assert "--soci-mode" not in result.stdout
    assert "--standalone" not in result.stdout


def test_soci_convert_rejects_unknown_option():
    runner = CliRunner()
    result = runner.invoke(app, ["soci", "convert", "meta.json", "--soci-mode", "containerd"])
    assert result.exit_code != 0
