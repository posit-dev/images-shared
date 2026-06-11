"""OrasWaitForSourcesWorkflow: pre-flight poll that waits for per-platform source digests to
become readable before the publish pipeline references them (GHCR read-after-write lag, #591)."""

from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.plugins.builtin.imagetools.oras import OrasWaitForSourcesWorkflow

pytestmark = [pytest.mark.unit]

_PROBE = "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow._is_available"


def test_dry_run_returns_success_without_probing():
    wf = OrasWaitForSourcesWorkflow(oras_bin="oras", sources=["a", "b"])
    sleep = MagicMock()
    with patch(_PROBE) as probe:
        result = wf.run(dry_run=True, sleep=sleep)
    assert result.success is True
    probe.assert_not_called()
    sleep.assert_not_called()


def test_empty_sources_returns_success():
    wf = OrasWaitForSourcesWorkflow(oras_bin="oras", sources=[])
    result = wf.run(sleep=MagicMock(), now=lambda: 0.0)
    assert result.success is True
    assert result.ready == []


def test_all_ready_on_first_sweep_does_not_sleep():
    wf = OrasWaitForSourcesWorkflow(oras_bin="oras", sources=["a", "b"])
    sleep = MagicMock()
    with patch(_PROBE, return_value=True):
        result = wf.run(sleep=sleep, now=lambda: 0.0)
    assert result.success is True
    assert result.ready == ["a", "b"]
    sleep.assert_not_called()


def test_waits_until_all_sources_ready():
    wf = OrasWaitForSourcesWorkflow(oras_bin="oras", sources=["a"], poll_interval=5.0, timeout=600.0)
    probes = {"n": 0}

    def probe(self, ref):
        probes["n"] += 1
        return probes["n"] >= 3  # readable on the third probe

    times = iter([0.0, 5.0, 10.0, 15.0])
    sleep = MagicMock()
    with patch(_PROBE, probe):
        result = wf.run(sleep=sleep, now=lambda: next(times))
    assert result.success is True
    assert result.ready == ["a"]
    assert sleep.call_count == 2  # slept before the 2nd and 3rd sweeps


def test_timeout_reports_missing_sources():
    wf = OrasWaitForSourcesWorkflow(oras_bin="oras", sources=["a", "b"], poll_interval=5.0, timeout=10.0)
    times = iter([0.0, 5.0, 10.0])
    sleep = MagicMock()
    with patch(_PROBE, return_value=False):
        result = wf.run(sleep=sleep, now=lambda: next(times))
    assert result.success is False
    assert set(result.missing) == {"a", "b"}
    assert result.error is not None
    assert "unreadable" in result.error


def test_dedups_sources():
    wf = OrasWaitForSourcesWorkflow(oras_bin="oras", sources=["a", "a", "b"])
    with patch(_PROBE, return_value=True):
        result = wf.run(sleep=MagicMock(), now=lambda: 0.0)
    assert result.ready == ["a", "b"]


class TestPublishPreflightWait:
    """ImageToolsPlugin.execute runs the pre-flight wait when the create phase is in scope."""

    def _target(self, uid="img-1-0-0"):
        from posit_bakery.image.image_target import ImageTarget, StringableList

        t = MagicMock(spec=ImageTarget)
        t.uid = uid
        t.image_name = "test-image"
        t.push_sort_key = (uid,)
        t.settings = MagicMock()
        t.settings.temp_registry = "ghcr.io/posit-dev"
        t.labels = {}
        t.get_merge_sources.return_value = ["ghcr.io/posit-dev/test/tmp@sha256:amd64"]
        tag = MagicMock()
        tag.destination = "ghcr.io/posit-dev/test-image"
        tag.suffix = "1.0.0"
        tag.__str__ = lambda self: "ghcr.io/posit-dev/test-image:1.0.0"
        t.tags = StringableList([tag])
        t.__str__ = lambda self: uid
        return t

    def _run(self, tmp_path, wait_result, phases):
        from posit_bakery.plugins.builtin.imagetools import ImageToolsPlugin
        from posit_bakery.plugins.builtin.imagetools.options import SociOptions

        wait_instance = MagicMock()
        wait_instance.run.return_value = wait_result
        with (
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
                return_value=wait_instance,
            ) as wait_cls,
            patch(
                "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
                return_value=SociOptions(enabled=False),
            ),
        ):
            results = ImageToolsPlugin().execute(tmp_path, [self._target()], phases=phases, dry_run=True)
        return wait_cls, wait_instance, results

    def test_wait_invoked_with_all_sources_then_publishes(self, tmp_path):
        from posit_bakery.plugins.builtin.imagetools.oras import OrasSourcesReadyResult
        from posit_bakery.plugins.builtin.imagetools.publish import ALL_PHASES

        wait_cls, wait_instance, results = self._run(
            tmp_path,
            OrasSourcesReadyResult(success=True, ready=["ghcr.io/posit-dev/test/tmp@sha256:amd64"]),
            ALL_PHASES,
        )
        _, kwargs = wait_cls.call_args
        assert kwargs["sources"] == ["ghcr.io/posit-dev/test/tmp@sha256:amd64"]
        wait_instance.run.assert_called_once()
        assert [r.exit_code for r in results] == [0]

    def test_wait_timeout_aborts_before_publishing(self, tmp_path):
        from posit_bakery.plugins.builtin.imagetools.oras import OrasSourcesReadyResult
        from posit_bakery.plugins.builtin.imagetools.publish import ALL_PHASES

        _, _, results = self._run(
            tmp_path,
            OrasSourcesReadyResult(success=False, missing=["x"], error="2 source digest(s) still unreadable"),
            ALL_PHASES,
        )
        assert [r.exit_code for r in results] == [1]
        assert "unreadable" in results[0].stderr

    def test_soci_only_phase_skips_wait(self, tmp_path):
        from posit_bakery.plugins.builtin.imagetools.publish import SOCI_PHASES

        wait_cls, wait_instance, results = self._run(tmp_path, None, SOCI_PHASES)
        wait_cls.assert_not_called()
