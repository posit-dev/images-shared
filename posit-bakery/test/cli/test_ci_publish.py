"""Tests for the `bakery ci publish` orchestrator."""

from unittest.mock import MagicMock, patch

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
    # SOCI is config-driven and standalone-only; there is no CLI flag for it.
    assert "--soci-mode" not in result.stdout
    assert "--enable-soci" not in result.stdout


def _fake_target(uid: str):
    t = MagicMock()
    t.uid = uid
    t.push_sort_key = 0
    t.get_merge_sources.return_value = []  # skip phase 1 (index-create)
    return t


def test_publish_invokes_soci_execute_without_mode(tmp_path):
    captured = {}

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid1"]
    fake_config.get_image_target_by_uid.return_value = _fake_target("uid1")

    fake_soci = MagicMock()

    def fake_execute(base_path, targets, *, source_refs=None, dry_run=False, **kwargs):
        captured["called"] = True
        captured["kwargs"] = kwargs
        return []

    fake_soci.execute.side_effect = fake_execute

    runner = CliRunner()
    with (
        patch("posit_bakery.cli.ci.BakeryConfig.from_context", return_value=fake_config),
        patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
        patch("posit_bakery.plugins.registry.get_plugin", return_value=fake_soci),
    ):
        result = runner.invoke(
            app,
            ["ci", "publish", "meta.json", "--dry-run"],
            env=_WIDE_TERM_ENV,
        )

    assert result.exit_code == 0, result.stdout
    assert captured["called"] is True
    # No mode/standalone selector is threaded through anymore.
    assert "standalone" not in captured["kwargs"]
