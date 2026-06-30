"""Tests for the `bakery ci publish` orchestrator.

The orchestration logic lives in the ``imagetools`` plugin
(``ImageToolsPlugin.publish``); ``bakery ci publish`` is a thin wrapper that
delegates to it.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from posit_bakery.cli.main import app
from posit_bakery.plugins.builtin.imagetools.oras import OrasIndexCopyWorkflow, OrasIndexCreateWorkflow

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
    # Default: no merge sources, which skips Stage 1 (wait + index-create +
    # soci-convert) entirely for this target.
    t.get_merge_sources.return_value = merge_sources or []
    # A bare MagicMock's `.image_version.parent.options` / `.image_variant.options`
    # iterate as empty (MagicMock auto-configures __iter__ to `iter([])`), so
    # get_soci_options_for_target(t) resolves to a real, defaulted SociOptions
    # (enabled=False) without any further configuration here.
    return t


def _bypass_pydantic_init(cls):
    """Patch ``cls.__init__`` to store constructor kwargs as plain attributes.

    ``OrasIndexCreateWorkflow``/``OrasIndexCopyWorkflow`` are pydantic ``BaseModel``s with an
    ``image_target: ImageTarget`` field; pydantic validates that field against the real
    ``ImageTarget`` model even with ``arbitrary_types_allowed=True`` (that setting only
    relaxes validation for genuinely-opaque types, not other pydantic models), so constructing
    one with a ``MagicMock`` target raises a validation error. These tests patch the
    workflow's ``run`` method directly (to control its result per-target), but construction
    still happens for real in ``_run_publish_stage1``/``publish()`` -- so construction itself
    must also be bypassed. Returns a context manager; the patched ``__init__`` only stores
    kwargs, so the patched ``run`` (and ``self.image_target`` accesses within it) keep working.
    """

    def fake_init(self, **kwargs):
        self.__dict__.update(kwargs)

    return patch.object(cls, "__init__", fake_init)


def test_publish_runs_stage1_per_target_then_copies_in_order(tmp_path):
    """Two targets: Stage 1 (wait+create+soci) runs for both via the parallel executor, then
    Stage 2 (index-copy) pushes them in push_sort_key order, then Stage 3 verifies both."""
    target_a = _fake_target("uid-a", merge_sources=["ghcr.io/posit-dev/test/tmp@sha256:a"])
    target_a.settings.temp_registry = "ghcr.io/posit-dev"
    target_a.push_sort_key = 1  # pushed second
    target_b = _fake_target("uid-b", merge_sources=["ghcr.io/posit-dev/test/tmp@sha256:b"])
    target_b.settings.temp_registry = "ghcr.io/posit-dev"
    target_b.push_sort_key = 0  # pushed first

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid-a", "uid-b"]
    fake_config.get_image_target_by_uid.side_effect = lambda uid: {"uid-a": target_a, "uid-b": target_b}[uid]

    wait_result = MagicMock(success=True, ready=["x"], missing=[], waited_seconds=0.1, error=None)
    create_result = MagicMock(success=True, temp_ref="ghcr.io/posit-dev/tmp:created")
    copy_order = []

    def fake_copy_run(self, source, dry_run=False):
        copy_order.append(self.image_target.uid)
        return MagicMock(success=True, destinations=["ghcr.io/posit-dev/test:1.0.0"], error=None)

    runner = CliRunner()
    with (
        patch("posit_bakery.cli.ci.BakeryConfig.from_context", return_value=fake_config),
        patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
        patch("posit_bakery.plugins.builtin.imagetools.soci.find_soci_bin", return_value="soci"),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
            return_value=MagicMock(run=MagicMock(return_value=wait_result)),
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow",
            return_value=MagicMock(run=MagicMock(return_value=create_result)),
        ),
        _bypass_pydantic_init(OrasIndexCopyWorkflow),
        patch("posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCopyWorkflow.run", fake_copy_run, create=True),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexVerifyWorkflow",
            return_value=MagicMock(
                run=MagicMock(return_value=MagicMock(success=True, verified=["ghcr.io/posit-dev/test:1.0.0"]))
            ),
        ),
    ):
        result = runner.invoke(app, ["ci", "publish", "meta.json"], env=_WIDE_TERM_ENV)

    assert result.exit_code == 0, result.stdout
    # Stage 2 pushes in push_sort_key order regardless of how Stage 1 completed.
    assert copy_order == ["uid-b", "uid-a"]


def test_publish_isolates_one_targets_create_failure_from_others(tmp_path):
    """One target's index-create failure must not prevent the other target from publishing,
    and the overall command must still exit non-zero."""
    failing = _fake_target("uid-fail", merge_sources=["ghcr.io/posit-dev/test/tmp@sha256:f"])
    failing.settings.temp_registry = "ghcr.io/posit-dev"
    ok = _fake_target("uid-ok", merge_sources=["ghcr.io/posit-dev/test/tmp@sha256:o"])
    ok.settings.temp_registry = "ghcr.io/posit-dev"

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid-fail", "uid-ok"]
    fake_config.get_image_target_by_uid.side_effect = lambda uid: {"uid-fail": failing, "uid-ok": ok}[uid]

    wait_result = MagicMock(success=True, ready=["x"], missing=[], waited_seconds=0.1, error=None)

    def fake_create_run(self, dry_run=False, runner=None):
        if self.image_target.uid == "uid-fail":
            return MagicMock(success=False, temp_ref=None, error="boom")
        return MagicMock(success=True, temp_ref="ghcr.io/posit-dev/tmp:created")

    copied = []

    def fake_copy_run(self, source, dry_run=False):
        copied.append(self.image_target.uid)
        return MagicMock(success=True, destinations=["ghcr.io/posit-dev/test:1.0.0"], error=None)

    runner = CliRunner()
    with (
        patch("posit_bakery.cli.ci.BakeryConfig.from_context", return_value=fake_config),
        patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
        patch("posit_bakery.plugins.builtin.imagetools.soci.find_soci_bin", return_value="soci"),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
            return_value=MagicMock(run=MagicMock(return_value=wait_result)),
        ),
        _bypass_pydantic_init(OrasIndexCreateWorkflow),
        patch("posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow.run", fake_create_run, create=True),
        _bypass_pydantic_init(OrasIndexCopyWorkflow),
        patch("posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCopyWorkflow.run", fake_copy_run, create=True),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexVerifyWorkflow",
            return_value=MagicMock(
                run=MagicMock(return_value=MagicMock(success=True, verified=["ghcr.io/posit-dev/test:1.0.0"]))
            ),
        ),
    ):
        result = runner.invoke(app, ["ci", "publish", "meta.json"], env=_WIDE_TERM_ENV)

    assert result.exit_code == 1
    # The failing target never reached Stage 2; the healthy target still published.
    assert copied == ["uid-ok"]


def test_publish_aborts_when_sources_never_ready(tmp_path):
    """A wait timeout for the only target fails that target (and, since it's the only
    target, the whole run) without raising."""
    sources = ["ghcr.io/posit-dev/test/tmp@sha256:amd64"]
    target = _fake_target("uid1", merge_sources=sources)
    target.settings.temp_registry = "ghcr.io/posit-dev"

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid1"]
    fake_config.get_image_target_by_uid.return_value = target

    wait_failure = MagicMock(success=False, ready=[], missing=sources, waited_seconds=600.0, error="still unreadable")

    runner = CliRunner()
    with (
        patch("posit_bakery.cli.ci.BakeryConfig.from_context", return_value=fake_config),
        patch("posit_bakery.plugins.builtin.imagetools.oras.find_oras_bin", return_value="oras"),
        patch("posit_bakery.plugins.builtin.imagetools.soci.find_soci_bin", return_value="soci"),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
            return_value=MagicMock(run=MagicMock(return_value=wait_failure)),
        ),
        patch("posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow") as mock_create,
    ):
        result = runner.invoke(app, ["ci", "publish", "meta.json"], env=_WIDE_TERM_ENV)

    assert result.exit_code == 1
    # Stage 1 never reached index-create for this target.
    mock_create.assert_not_called()


def test_publish_surfaces_clean_error_on_non_transient_wait_failure(tmp_path):
    """A non-transient registry error during the wait exits cleanly (code 1) rather than
    escaping as an unhandled traceback."""
    from posit_bakery.error import BakeryToolRuntimeError

    sources = ["ghcr.io/posit-dev/test/tmp@sha256:amd64"]
    target = _fake_target("uid1", merge_sources=sources)
    target.settings.temp_registry = "ghcr.io/posit-dev"

    fake_config = MagicMock()
    fake_config.base_path = tmp_path
    fake_config.load_build_metadata_from_file.return_value = ["uid1"]
    fake_config.get_image_target_by_uid.return_value = target

    error = BakeryToolRuntimeError(
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
        patch("posit_bakery.plugins.builtin.imagetools.soci.find_soci_bin", return_value="soci"),
        patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
            return_value=MagicMock(run=MagicMock(side_effect=error)),
        ),
        patch("posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow") as mock_create,
    ):
        result = runner.invoke(app, ["ci", "publish", "meta.json"], env=_WIDE_TERM_ENV)

    assert result.exit_code == 1
    assert result.exception is None or isinstance(result.exception, SystemExit)
    mock_create.assert_not_called()
