"""Tests for SociPlugin.execute()."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.soci import SociPlugin
from posit_bakery.plugins.builtin.soci.options import SociOptions

pytestmark = [pytest.mark.unit]


def _make_target(uid: str, enabled: bool, image_name: str = "test-image") -> ImageTarget:
    t = MagicMock(spec=ImageTarget)
    t.uid = uid
    t.image_name = image_name
    t.temp_registry = "ghcr.io/posit-dev"
    t.__str__ = lambda self: f"ImageTarget({uid})"
    # Plugin reads SociOptions from target.image_version.parent.options or
    # target.image_variant.options. For unit testing the plugin's gating
    # behavior we let the plugin call get_soci_options(target) which we
    # patch out via the helper exposed on the plugin module.
    return t


def test_skips_targets_without_enabled_option(tmp_path):
    plugin = SociPlugin()
    t_off = _make_target("a", enabled=False)
    t_on = _make_target("b", enabled=True)

    def fake_options(target):
        return SociOptions(enabled=(target.uid == "b"))

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            side_effect=fake_options,
        ),
        patch(
            "posit_bakery.plugins.builtin.soci.find_soci_bin",
            return_value="soci",
        ),
        patch(
            "posit_bakery.plugins.builtin.soci.find_ctr_bin",
            return_value="ctr",
        ),
        patch(
            "posit_bakery.plugins.builtin.soci.find_oras_bin",
            return_value="oras",
        ),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        # source_ref is provided via kwargs from the orchestrator. For the
        # test we set it explicitly via per-target kwargs map.
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t_off, t_on],
            source_refs={"a": "ref-a", "b": "ref-b"},
        )

    assert len(results) == 2
    off_result = next(r for r in results if r.target.uid == "a")
    on_result = next(r for r in results if r.target.uid == "b")
    assert off_result.exit_code == 0
    assert off_result.artifacts is not None
    assert off_result.artifacts.get("skipped") is True
    assert on_result.exit_code == 0
    assert on_result.artifacts is not None
    assert on_result.artifacts["workflow_result"].success is True


def test_logs_summary_when_no_enabled_targets(tmp_path, caplog):
    plugin = SociPlugin()
    t = _make_target("a", enabled=False)

    import logging

    caplog.set_level(logging.INFO, logger="posit_bakery.plugins.builtin.soci")
    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=False),
        ),
        patch(
            "posit_bakery.plugins.builtin.soci.find_soci_bin",
            return_value="soci",
        ),
        patch(
            "posit_bakery.plugins.builtin.soci.find_ctr_bin",
            return_value="ctr",
        ),
        patch(
            "posit_bakery.plugins.builtin.soci.find_oras_bin",
            return_value="oras",
        ),
    ):
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
        )

    assert len(results) == 1
    assert results[0].artifacts.get("skipped") is True
    assert "no targets have soci enabled" in caplog.text.lower()


def test_no_eligible_targets_does_not_invoke_binary_lookup(tmp_path):
    """When all targets are disabled, execute should not require soci/ctr
    binaries to be installed — the lookups should be skipped."""
    plugin = SociPlugin()
    t = _make_target("a", enabled=False)

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=False),
        ),
        patch(
            "posit_bakery.plugins.builtin.soci.find_soci_bin",
        ) as mock_find_soci,
        patch(
            "posit_bakery.plugins.builtin.soci.find_ctr_bin",
        ) as mock_find_ctr,
        patch(
            "posit_bakery.plugins.builtin.soci.find_oras_bin",
        ) as mock_find_oras,
    ):
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
        )

    assert len(results) == 1
    assert results[0].artifacts.get("skipped") is True
    mock_find_soci.assert_not_called()
    mock_find_ctr.assert_not_called()
    mock_find_oras.assert_not_called()
