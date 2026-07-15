"""Tests for the imagetools CLI commands (`bakery imagetools merge` /
`bakery imagetools soci-convert`) and their hidden back-compat aliases
(`bakery oras merge` / `bakery soci convert`)."""

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [pytest.mark.unit]

# Force a wide, unstyled terminal so rich/typer doesn't line-wrap option
# names across rows with embedded ANSI escapes, which defeats substring
# assertions on narrow CI terminals.
_WIDE_TERM_ENV = {"COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"}


def test_imagetools_help_lists_subcommands():
    runner = CliRunner()
    result = runner.invoke(app, ["imagetools", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0
    assert "merge" in result.stdout
    assert "soci-convert" in result.stdout


def test_soci_convert_requires_metadata_file_argument():
    runner = CliRunner()
    result = runner.invoke(app, ["imagetools", "soci-convert"])
    assert result.exit_code != 0


def test_soci_convert_help_has_no_mode_option():
    runner = CliRunner()
    result = runner.invoke(app, ["imagetools", "soci-convert", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0
    # Conversion is standalone-only; there is no mode selector.
    assert "--soci-mode" not in result.stdout
    assert "--standalone" not in result.stdout


def test_soci_convert_rejects_unknown_option():
    runner = CliRunner()
    result = runner.invoke(app, ["imagetools", "soci-convert", "meta.json", "--soci-mode", "containerd"])
    assert result.exit_code != 0


def test_merge_requires_metadata_file_argument():
    runner = CliRunner()
    result = runner.invoke(app, ["imagetools", "merge"])
    assert result.exit_code != 0


# --- Hidden back-compat aliases still resolve ---


def test_hidden_soci_convert_alias_still_works():
    runner = CliRunner()
    result = runner.invoke(app, ["soci", "convert", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0


def test_hidden_oras_merge_alias_still_works():
    runner = CliRunner()
    result = runner.invoke(app, ["oras", "merge", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0
