"""Tests for SociPlugin.execute()."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import posit_bakery.util as util
from posit_bakery.error import BakeryToolNotFoundError
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.soci import SociPlugin
from posit_bakery.plugins.builtin.soci.options import SociOptions
from posit_bakery.plugins.builtin.soci.soci import SociConvertWorkflowResult

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
            standalone=False,
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
    plugin = SociPlugin()
    t_ref = _make_target("a", enabled=True)
    t_noref = _make_target("b", enabled=True)

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("posit_bakery.plugins.builtin.soci.find_soci_bin", return_value="soci"),
        patch("posit_bakery.plugins.builtin.soci.find_ctr_bin", return_value="ctr"),
        patch("posit_bakery.plugins.builtin.soci.find_oras_bin", return_value="oras"),
        patch("subprocess.run") as mock_run,
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t_ref, t_noref],
            source_refs={"a": "ref-a"},
            standalone=False,
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


@pytest.fixture
def missing_tools(monkeypatch):
    """Simulate a host where soci/ctr/oras are not installed anywhere."""
    real_which = util.which
    monkeypatch.setattr(util, "which", lambda name: None if name in {"soci", "ctr", "oras"} else real_which(name))
    for env in ("SOCI_PATH", "CTR_PATH", "ORAS_PATH"):
        monkeypatch.delenv(env, raising=False)


@pytest.mark.parametrize("standalone", [False, True])
def test_dry_run_does_not_require_tools_installed(tmp_path, missing_tools, standalone):
    """A dry-run executes nothing, so it must not abort when soci/ctr/oras are
    absent from the host. Regression: ``ci publish --dry-run`` raised
    BakeryToolNotFoundError because execute() resolved the binaries eagerly,
    before the dry-run-aware workflow ran."""
    plugin = SociPlugin()
    t = _make_target("a", enabled=True)

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("subprocess.run") as mock_run,
        patch(
            "posit_bakery.plugins.builtin.soci.soci.SociConvertWorkflow._read_converted_digest",
            return_value="sha256:abc",
        ),
    ):
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
            dry_run=True,
            standalone=standalone,
        )

    mock_run.assert_not_called()
    assert [r.exit_code for r in results] == [0]


def test_dry_run_uses_resolved_path_when_tool_present(tmp_path, monkeypatch):
    """When a tool IS resolvable, the dry-run still surfaces its real path
    (env var / PATH / project tools dir) rather than a bare fallback name, so
    the logged commands remain accurate."""
    monkeypatch.setenv("SOCI_PATH", "/custom/soci")
    monkeypatch.setenv("CTR_PATH", "/custom/ctr")
    monkeypatch.setenv("ORAS_PATH", "/custom/oras")
    plugin = SociPlugin()
    t = _make_target("a", enabled=True)

    captured = {}

    def fake_run(self, dry_run=False):
        captured["soci_bin"] = self.soci_bin
        captured["ctr_bin"] = self.ctr_bin
        captured["oras_bin"] = self.oras_bin
        from posit_bakery.plugins.builtin.soci.soci import SociConvertWorkflowResult

        return SociConvertWorkflowResult(success=True, destination_ref=self.destination_ref)

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("posit_bakery.plugins.builtin.soci.soci.SociConvertWorkflow.run", fake_run),
    ):
        plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
            dry_run=True,
        )

    assert captured["soci_bin"] == "/custom/soci"
    assert captured["ctr_bin"] == "/custom/ctr"
    assert captured["oras_bin"] == "/custom/oras"


def test_standalone_run_does_not_require_ctr(tmp_path, monkeypatch):
    """Standalone mode never touches containerd, so a real (non-dry-run)
    standalone conversion must not require `ctr` to be installed — only the
    tools it actually executes (soci, oras)."""
    monkeypatch.setenv("SOCI_PATH", "/custom/soci")
    monkeypatch.setenv("ORAS_PATH", "/custom/oras")
    monkeypatch.delenv("CTR_PATH", raising=False)
    monkeypatch.setattr(util, "which", lambda name: None)
    plugin = SociPlugin()
    t = _make_target("a", enabled=True)

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("subprocess.run") as mock_run,
        patch(
            "posit_bakery.plugins.builtin.soci.soci.SociConvertWorkflow._read_converted_digest",
            return_value="sha256:abc",
        ),
    ):
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"", stderr=b"")
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
            dry_run=False,
            standalone=True,
        )

    assert [r.exit_code for r in results] == [0]


def test_non_standalone_run_still_requires_ctr(tmp_path, monkeypatch):
    """A real (non-dry-run) containerd-backed conversion does use `ctr`, so a
    missing `ctr` must remain a hard error."""
    monkeypatch.setenv("SOCI_PATH", "/custom/soci")
    monkeypatch.setenv("ORAS_PATH", "/custom/oras")
    monkeypatch.delenv("CTR_PATH", raising=False)
    monkeypatch.setattr(util, "which", lambda name: None)
    plugin = SociPlugin()
    t = _make_target("a", enabled=True)

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("subprocess.run"),
        pytest.raises(BakeryToolNotFoundError),
    ):
        plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
            dry_run=False,
            standalone=False,
        )


def test_execute_defaults_to_standalone_mode(tmp_path):
    """execute() now defaults to standalone mode when no mode is passed."""
    plugin = SociPlugin()
    t = _make_target("a", enabled=True)

    captured = {}

    def fake_run(self, dry_run=False):
        captured["standalone"] = self.standalone
        return SociConvertWorkflowResult(success=True, destination_ref=self.destination_ref)

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch("posit_bakery.plugins.builtin.soci.find_soci_bin", return_value="soci"),
        patch("posit_bakery.plugins.builtin.soci.find_ctr_bin", return_value="ctr"),
        patch("posit_bakery.plugins.builtin.soci.find_oras_bin", return_value="oras"),
        patch("posit_bakery.plugins.builtin.soci.soci.SociConvertWorkflow.run", fake_run),
    ):
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
        )

    assert captured["standalone"] is True
    assert [r.exit_code for r in results] == [0]


def test_containerd_run_resolves_sudo_once_and_threads_it(tmp_path, monkeypatch):
    """A real containerd run resolves the sudo prefix once and passes the
    resulting `sudo` flag into the workflow."""
    monkeypatch.setenv("SOCI_PATH", "/custom/soci")
    monkeypatch.setenv("CTR_PATH", "/custom/ctr")
    monkeypatch.setenv("ORAS_PATH", "/custom/oras")
    plugin = SociPlugin()
    t = _make_target("a", enabled=True)

    captured = {}

    def fake_run(self, dry_run=False):
        captured["sudo"] = self.sudo
        return SociConvertWorkflowResult(success=True, destination_ref=self.destination_ref)

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch(
            "posit_bakery.plugins.builtin.soci.soci.resolve_sudo_prefix",
            return_value=["sudo", "-n"],
        ) as mock_resolve,
        patch("posit_bakery.plugins.builtin.soci.soci.SociConvertWorkflow.run", fake_run),
    ):
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
            dry_run=False,
            standalone=False,
        )

    assert [r.exit_code for r in results] == [0]
    assert captured["sudo"] is True
    mock_resolve.assert_called_once()


def test_containerd_run_fails_fast_when_sudo_would_prompt(tmp_path, monkeypatch):
    """When privilege resolution raises, the run reports a single failure and
    does not invoke the workflow."""
    from posit_bakery.plugins.builtin.soci.soci import SociPrivilegeError

    monkeypatch.setenv("SOCI_PATH", "/custom/soci")
    monkeypatch.setenv("CTR_PATH", "/custom/ctr")
    monkeypatch.setenv("ORAS_PATH", "/custom/oras")
    plugin = SociPlugin()
    t = _make_target("a", enabled=True)

    def boom(self, dry_run=False):
        raise AssertionError("workflow should not run when privilege resolution fails")

    with (
        patch(
            "posit_bakery.plugins.builtin.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=True),
        ),
        patch(
            "posit_bakery.plugins.builtin.soci.soci.resolve_sudo_prefix",
            side_effect=SociPrivilegeError("needs root"),
        ),
        patch("posit_bakery.plugins.builtin.soci.soci.SociConvertWorkflow.run", boom),
    ):
        results = plugin.execute(
            base_path=tmp_path,
            targets=[t],
            source_refs={"a": "ref-a"},
            dry_run=False,
            standalone=False,
        )

    assert len(results) == 1
    assert results[0].exit_code == 1
    assert "needs root" in results[0].stderr
