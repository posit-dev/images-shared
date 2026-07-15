"""Tests for ImageToolsPlugin.execute() (SOCI conversion)."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

import posit_bakery.util as util
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.imagetools import ImageToolsPlugin
from posit_bakery.plugins.builtin.imagetools.options import SociOptions
from posit_bakery.plugins.builtin.imagetools.soci import SociConvertWorkflow, SociConvertWorkflowResult

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
    plugin = ImageToolsPlugin()
    t_off = _make_target("a", enabled=False)
    t_on = _make_target("b", enabled=True)

    def fake_options(target):
        return SociOptions(enabled=(target.uid == "b"))

    with (
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.get_soci_options_for_target",
            side_effect=fake_options,
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.find_soci_bin",
            return_value="soci",
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.find_oras_bin",
            return_value="oras",
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.soci.SociConvertWorkflow._read_converted_digest",
            return_value="sha256:abc",
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


def test_enabled_target_without_source_ref_is_skipped_not_failed(tmp_path):
    """A SOCI-enabled target with no source ref for this run is not in scope
    (e.g. it has no merge sources / build metadata in the provided files, like
    other versions/streams when publishing one set of metadata). It must be
    skipped, not reported as a conversion failure. Regression: such targets
    surfaced as "SOCI convert failed: no source ref provided" and flipped the
    whole `ci publish` run to a failure."""
    plugin = ImageToolsPlugin()
    t_ref = _make_target("a", enabled=True)
    t_noref = _make_target("b", enabled=True)

    with (
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("posit_bakery.plugins.builtin.imagetools.imagetools.find_soci_bin", return_value="soci"),
        patch("posit_bakery.plugins.builtin.imagetools.imagetools.find_oras_bin", return_value="oras"),
        patch(
            "posit_bakery.plugins.builtin.imagetools.soci.SociConvertWorkflow._read_converted_digest",
            return_value="sha256:abc",
        ),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t_ref, t_noref],
            source_refs={"a": "ref-a"},
        )

    noref = next(r for r in results if r.target.uid == "b")
    assert noref.exit_code == 0
    assert noref.artifacts is not None
    assert noref.artifacts.get("skipped") is True
    # The in-scope target still converts.
    ref = next(r for r in results if r.target.uid == "a")
    assert ref.exit_code == 0
    assert ref.artifacts["workflow_result"].success is True


def test_logs_summary_when_no_enabled_targets(tmp_path, caplog):
    plugin = ImageToolsPlugin()
    t = _make_target("a", enabled=False)

    import logging

    caplog.set_level(logging.INFO, logger="posit_bakery.plugins.builtin.imagetools.imagetools")
    with (
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.get_soci_options_for_target",
            return_value=SociOptions(enabled=False),
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.find_soci_bin",
            return_value="soci",
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.find_oras_bin",
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
    """When all targets are disabled, execute should not require soci/oras
    binaries to be installed — the lookups should be skipped."""
    plugin = ImageToolsPlugin()
    t = _make_target("a", enabled=False)

    with (
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.get_soci_options_for_target",
            return_value=SociOptions(enabled=False),
        ),
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.find_soci_bin",
        ) as mock_find_soci,
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.find_oras_bin",
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
    mock_find_oras.assert_not_called()


@pytest.fixture
def missing_tools(monkeypatch):
    """Simulate a host where soci/oras are not installed anywhere."""
    real_which = util.which
    monkeypatch.setattr(util, "which", lambda name: None if name in {"soci", "oras"} else real_which(name))
    for env in ("SOCI_PATH", "ORAS_PATH"):
        monkeypatch.delenv(env, raising=False)


def test_dry_run_does_not_require_tools_installed(tmp_path, missing_tools):
    """A dry-run executes nothing, so it must not abort when soci/oras are
    absent from the host. Regression: ``ci publish --dry-run`` raised
    BakeryToolNotFoundError because execute() resolved the binaries eagerly,
    before the dry-run-aware workflow ran."""
    plugin = ImageToolsPlugin()
    t = _make_target("a", enabled=True)

    with (
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("subprocess.run") as mock_run,
        patch(
            "posit_bakery.plugins.builtin.imagetools.soci.SociConvertWorkflow._read_converted_digest",
            return_value="sha256:abc",
        ),
    ):
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
            dry_run=True,
        )

    mock_run.assert_not_called()
    assert [r.exit_code for r in results] == [0]


def test_dry_run_uses_resolved_path_when_tool_present(tmp_path, monkeypatch):
    """When a tool IS resolvable, the dry-run still surfaces its real path
    (env var / PATH / project tools dir) rather than a bare fallback name, so
    the logged commands remain accurate."""
    monkeypatch.setenv("SOCI_PATH", "/custom/soci")
    monkeypatch.setenv("ORAS_PATH", "/custom/oras")
    plugin = ImageToolsPlugin()
    t = _make_target("a", enabled=True)

    captured = {}

    def fake_run(self, dry_run=False):
        captured["soci_bin"] = self.soci_bin
        captured["oras_bin"] = self.oras_bin
        return SociConvertWorkflowResult(success=True, destination_ref=self.destination_ref)

    with (
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("posit_bakery.plugins.builtin.imagetools.soci.SociConvertWorkflow.run", fake_run),
    ):
        plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
            dry_run=True,
        )

    assert captured["soci_bin"] == "/custom/soci"
    assert captured["oras_bin"] == "/custom/oras"


def test_run_does_not_require_ctr(tmp_path, monkeypatch):
    """Conversion never touches containerd, so a real (non-dry-run) conversion
    must not require `ctr` to be installed — only the tools it actually
    executes (soci, oras)."""
    monkeypatch.setenv("SOCI_PATH", "/custom/soci")
    monkeypatch.setenv("ORAS_PATH", "/custom/oras")
    monkeypatch.delenv("CTR_PATH", raising=False)
    monkeypatch.setattr(util, "which", lambda name: None)
    plugin = ImageToolsPlugin()
    t = _make_target("a", enabled=True)

    with (
        patch(
            "posit_bakery.plugins.builtin.imagetools.imagetools.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("subprocess.run") as mock_run,
        patch(
            "posit_bakery.plugins.builtin.imagetools.soci.SociConvertWorkflow._read_converted_digest",
            return_value="sha256:abc",
        ),
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
            dry_run=False,
        )

    assert [r.exit_code for r in results] == [0]
