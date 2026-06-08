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
    assert "--soci-mode" in result.stdout
    # SOCI is config-driven; there is no longer a CLI flag for it.
    assert "--enable-soci" not in result.stdout


def _fake_target(uid: str):
    t = MagicMock()
    t.uid = uid
    t.push_sort_key = 0
    t.get_merge_sources.return_value = []  # skip phase 1 (index-create)
    return t


@pytest.mark.parametrize(
    ("mode_args", "expected_standalone"),
    [
        ([], True),  # default
        (["--soci-mode", "standalone"], True),
        (["--soci-mode", "containerd"], False),
    ],
)
def test_publish_passes_soci_mode_to_execute(tmp_path, mode_args, expected_standalone):
    captured = {}

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid1"]
    fake_config.get_image_target_by_uid.return_value = _fake_target("uid1")

    fake_soci = MagicMock()

    def fake_execute(base_path, targets, *, source_refs=None, dry_run=False, standalone, **kwargs):
        captured["standalone"] = standalone
        return []

    fake_soci.execute.side_effect = fake_execute

    runner = CliRunner()
    with (
        patch("posit_bakery.cli.ci.BakeryConfig.from_context", return_value=fake_config),
        patch("posit_bakery.plugins.builtin.oras.oras.find_oras_bin", return_value="oras"),
        patch("posit_bakery.plugins.registry.get_plugin", return_value=fake_soci),
    ):
        result = runner.invoke(
            app,
            ["ci", "publish", "meta.json", "--dry-run", *mode_args],
            env=_WIDE_TERM_ENV,
        )

    assert result.exit_code == 0, result.stdout
    assert captured["standalone"] is expected_standalone
