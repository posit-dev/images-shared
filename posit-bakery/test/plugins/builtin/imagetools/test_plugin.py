"""ImageToolsPlugin.execute(): fan targets out across the parallel executor and map each
PublishResult onto a ToolCallResult; results() summarizes and exits non-zero on failure."""

from unittest.mock import MagicMock, patch

import pytest
import typer

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.imagetools import ImageToolsPlugin
from posit_bakery.plugins.builtin.imagetools.publish import PublishResult, PublishWorkflow
from posit_bakery.plugins.builtin.imagetools.options import SociOptions

pytestmark = [pytest.mark.unit]


def _make_target(uid, push_sort_key=0):
    t = MagicMock(spec=ImageTarget)
    t.uid = uid
    t.image_name = "test-image"
    t.push_sort_key = push_sort_key
    t.__str__ = lambda self: f"ImageTarget({uid})"
    return t


def _patches():
    """Patch bin resolution and soci-option lookup so execute() runs without real tools."""
    return (
        patch("posit_bakery.plugins.builtin.imagetools.find_oras_bin", return_value="oras"),
        patch("posit_bakery.plugins.builtin.imagetools.find_soci_bin", return_value="soci"),
        patch(
            "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
            return_value=SociOptions(enabled=False),
        ),
    )


def _run_with(fake_run, targets, tmp_path, **kwargs):
    plugin = ImageToolsPlugin()
    p_oras, p_soci, p_opts = _patches()
    with p_oras, p_soci, p_opts, patch.object(PublishWorkflow, "run", fake_run):
        return plugin, plugin.execute(tmp_path, targets, dry_run=True, **kwargs)


class TestExecute:
    def test_one_result_per_target_ordered_by_push_sort_key(self, tmp_path):
        def fake_run(self, runner, *, phases, dry_run):
            return PublishResult(target=self.image_target, success=True, verified=["t"])

        _, results = _run_with(fake_run, [_make_target("b", 2), _make_target("a", 1)], tmp_path)
        assert [r.target.uid for r in results] == ["a", "b"]
        assert all(r.exit_code == 0 for r in results)

    def test_skipped_target_maps_to_skipped_artifact(self, tmp_path):
        def fake_run(self, runner, *, phases, dry_run):
            return PublishResult(target=self.image_target, skipped=True, skip_reason="no merge sources")

        _, results = _run_with(fake_run, [_make_target("a")], tmp_path)
        assert results[0].exit_code == 0
        assert results[0].artifacts.get("skipped") is True

    def test_failed_target_maps_to_nonzero_exit(self, tmp_path):
        def fake_run(self, runner, *, phases, dry_run):
            return PublishResult(target=self.image_target, success=False, error="copy boom", failed_phase="copy")

        _, results = _run_with(fake_run, [_make_target("a")], tmp_path)
        assert results[0].exit_code == 1
        assert "copy boom" in results[0].stderr

    def test_exception_in_job_maps_to_nonzero_exit(self, tmp_path):
        def fake_run(self, runner, *, phases, dry_run):
            raise RuntimeError("kaboom")

        _, results = _run_with(fake_run, [_make_target("a")], tmp_path)
        assert results[0].exit_code == 1


class TestResults:
    def test_results_exits_nonzero_when_any_failed(self, tmp_path):
        def fake_run(self, runner, *, phases, dry_run):
            return PublishResult(target=self.image_target, success=False, error="boom", failed_phase="create")

        plugin, results = _run_with(fake_run, [_make_target("a")], tmp_path)
        with pytest.raises(typer.Exit) as exc:
            plugin.results(results)
        assert exc.value.exit_code == 1

    def test_results_succeeds_when_all_ok(self, tmp_path):
        def fake_run(self, runner, *, phases, dry_run):
            return PublishResult(target=self.image_target, success=True)

        plugin, results = _run_with(fake_run, [_make_target("a")], tmp_path)
        plugin.results(results)  # no raise
