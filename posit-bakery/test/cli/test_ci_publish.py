"""Tests for the `bakery ci publish` orchestrator.

The orchestration logic lives in the ``imagetools`` plugin
(``ImageToolsPlugin.publish``); ``bakery ci publish`` is a thin wrapper that
delegates to it.
"""

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


def _fake_target(uid: str, merge_sources: list[str] | None = None):
    t = MagicMock()
    t.uid = uid
    t.push_sort_key = 0
    # Default: no merge sources, which skips phase 1 (index-create) and the
    # pre-flight source wait.
    t.get_merge_sources.return_value = merge_sources or []
    return t


def test_publish_invokes_soci_convert_without_mode(tmp_path):
    """`ci publish` should drive the plugin's SOCI conversion phase
    (``ImageToolsPlugin.execute``) without threading any mode/standalone
    selector through it."""
    captured = {}

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid1"]
    fake_config.get_image_target_by_uid.return_value = _fake_target("uid1")

    def fake_execute(self, base_path, targets, *, source_refs=None, dry_run=False, **kwargs):
        captured["called"] = True
        captured["kwargs"] = kwargs
        return []

    runner = CliRunner()
    with (
        patch("posit_bakery.config.BakeryConfig.from_context", return_value=fake_config),
        patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.ImageToolsPlugin.execute",
            autospec=True,
            side_effect=fake_execute,
        ),
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


def test_publish_waits_for_sources_then_proceeds(tmp_path):
    """The pre-flight wait is invoked with the targets' merge-source digests.

    The orchestration now lives in ``ImageToolsPlugin.publish``; its SOCI
    convert phase (``ImageToolsPlugin.execute``) is stubbed so we can exercise
    the path from the wait through the ORAS phases.
    """
    sources = [
        "ghcr.io/posit-dev/test/tmp@sha256:amd64",
        "ghcr.io/posit-dev/test/tmp@sha256:arm64",
    ]
    target = _fake_target("uid1", merge_sources=sources)
    target.settings.temp_registry = "ghcr.io/posit-dev"

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid1"]
    fake_config.get_image_target_by_uid.return_value = target

    captured = {}

    fake_wait_instance = MagicMock()
    fake_wait_instance.run.return_value = MagicMock(success=True, ready=sources, missing=[], waited_seconds=3.0)

    def fake_wait_ctor(**kwargs):
        captured["wait_kwargs"] = kwargs
        return fake_wait_instance

    # Make the downstream phases succeed so we exercise the path past the wait.
    fake_create_result = MagicMock(success=True, temp_ref="ghcr.io/posit-dev/test/tmp:created")
    fake_copy_result = MagicMock(success=True, destinations=["ghcr.io/posit-dev/test:1.0.0"], error=None)
    fake_verify_result = MagicMock(success=True, verified=["ghcr.io/posit-dev/test:1.0.0"], error=None)

    runner = CliRunner()
    with (
        patch("posit_bakery.cli.ci.BakeryConfig.from_context", return_value=fake_config),
        patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
        patch("posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow", side_effect=fake_wait_ctor),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow",
            return_value=MagicMock(run=MagicMock(return_value=fake_create_result)),
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCopyWorkflow",
            return_value=MagicMock(run=MagicMock(return_value=fake_copy_result)),
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexVerifyWorkflow",
            return_value=MagicMock(run=MagicMock(return_value=fake_verify_result)),
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.ImageToolsPlugin.execute",
            autospec=True,
            return_value=[],
        ),
    ):
        result = runner.invoke(app, ["ci", "publish", "meta.json"], env=_WIDE_TERM_ENV)

    assert result.exit_code == 0, result.stdout
    fake_wait_instance.run.assert_called_once()
    assert sorted(captured["wait_kwargs"]["sources"]) == sorted(sources)


def test_publish_aborts_when_sources_never_ready(tmp_path):
    """A wait timeout aborts the publish before any phase runs."""
    sources = ["ghcr.io/posit-dev/test/tmp@sha256:amd64"]
    target = _fake_target("uid1", merge_sources=sources)
    target.settings.temp_registry = "ghcr.io/posit-dev"

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid1"]
    fake_config.get_image_target_by_uid.return_value = target

    fake_wait_instance = MagicMock()
    fake_wait_instance.run.return_value = MagicMock(
        success=False, ready=[], missing=sources, waited_seconds=600.0, error="still unreadable"
    )

    runner = CliRunner()
    with (
        patch("posit_bakery.cli.ci.BakeryConfig.from_context", return_value=fake_config),
        patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
            return_value=fake_wait_instance,
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.ImageToolsPlugin.execute",
            autospec=True,
        ) as mock_execute,
    ):
        result = runner.invoke(app, ["ci", "publish", "meta.json"], env=_WIDE_TERM_ENV)

    assert result.exit_code == 1
    # Aborted before SOCI convert.
    mock_execute.assert_not_called()


def test_publish_surfaces_clean_error_on_non_transient_wait_failure(tmp_path):
    """A non-transient registry error during the wait exits cleanly (code 1)
    rather than escaping as an unhandled traceback."""
    from posit_bakery.error import BakeryToolRuntimeError

    sources = ["ghcr.io/posit-dev/test/tmp@sha256:amd64"]
    target = _fake_target("uid1", merge_sources=sources)
    target.settings.temp_registry = "ghcr.io/posit-dev"

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid1"]
    fake_config.get_image_target_by_uid.return_value = target

    fake_wait_instance = MagicMock()
    fake_wait_instance.run.side_effect = BakeryToolRuntimeError(
        message="oras command failed",
        tool_name="oras",
        cmd=["oras", "manifest", "fetch"],
        stdout=b"",
        stderr=b"unauthorized: authentication required",
    )

    runner = CliRunner()
    with (
        patch("posit_bakery.cli.ci.BakeryConfig.from_context", return_value=fake_config),
        patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
            return_value=fake_wait_instance,
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.ImageToolsPlugin.execute",
            autospec=True,
        ) as mock_execute,
    ):
        result = runner.invoke(app, ["ci", "publish", "meta.json"], env=_WIDE_TERM_ENV)

    # Clean exit, not an unhandled exception.
    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    mock_execute.assert_not_called()
