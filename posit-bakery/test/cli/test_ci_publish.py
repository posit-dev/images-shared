"""Tests for the `bakery ci publish` orchestrator."""

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app

pytestmark = [pytest.mark.unit]

# Force a wide, unstyled terminal so rich/typer doesn't line-wrap long option
# names across rows with embedded ANSI escapes, which defeats substring
# assertions on narrow CI terminals.
_WIDE_TERM_ENV = {"COLUMNS": "200", "TERM": "dumb", "NO_COLOR": "1"}


def test_publish_help_lists_command():
    runner = CliRunner()
    result = runner.invoke(app, ["ci", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0
    assert "publish" in result.stdout


def test_publish_command_flags_present():
    runner = CliRunner()
    result = runner.invoke(app, ["ci", "publish", "--help"], env=_WIDE_TERM_ENV)
    assert result.exit_code == 0
    assert "--temp-registry" in result.stdout
    assert "--dry-run" in result.stdout
    # SOCI is config-driven; there is no longer a CLI flag for it.
    assert "--enable-soci" not in result.stdout
