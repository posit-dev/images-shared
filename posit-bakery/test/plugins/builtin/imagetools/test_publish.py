"""PublishWorkflow: per-target create -> soci -> copy -> verify sequencing, driven through a
CommandRunner. A StubRunner stands in for the executor-bound runner and records the command
sequence each phase emits."""

from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.image.image_target import ImageTarget, StringableList
from posit_bakery.parallel import CommandResult
from posit_bakery.plugins.builtin.imagetools.publish import (
    ALL_PHASES,
    MERGE_PHASES,
    SOCI_PHASES,
    PublishPhase,
    PublishWorkflow,
)
from posit_bakery.plugins.builtin.imagetools.options import SociOptions

pytestmark = [pytest.mark.unit]


class StubRunner:
    """Returns ok CommandResults and records every command + step_label it runs."""

    def __init__(self, fail_on=None):
        self.calls = []
        self._fail_on = fail_on  # substring to fail on (in joined cmd), else all succeed

    def run(self, cmd, *, env=None, cwd=None, timeout=None, retry=None, step_label=None):
        self.calls.append({"cmd": cmd, "step_label": step_label})
        joined = " ".join(cmd)
        if self._fail_on and self._fail_on in joined:
            return CommandResult(cmd=cmd, returncode=1, stdout=b"", stderr=b"not found", duration=0.0)
        return CommandResult(cmd=cmd, returncode=0, stdout=b"", stderr=b"", duration=0.0)

    def step_labels(self):
        return [c["step_label"] for c in self.calls]


def _make_target(uid="img-1-0-0", image_name="test-image", with_merge_sources=True):
    t = MagicMock(spec=ImageTarget)
    t.uid = uid
    t.image_name = image_name
    t.temp_registry = "ghcr.io/posit-dev"
    t.settings = MagicMock()
    t.settings.temp_registry = "ghcr.io/posit-dev"
    t.labels = {"org.opencontainers.image.title": "Test Image"}
    t.get_merge_sources.return_value = (
        ["ghcr.io/posit-dev/test/tmp@sha256:amd64", "ghcr.io/posit-dev/test/tmp@sha256:arm64"]
        if with_merge_sources
        else []
    )
    tag = MagicMock()
    tag.destination = "ghcr.io/posit-dev/test-image"
    tag.suffix = "1.0.0"
    tag.__str__ = lambda self: "ghcr.io/posit-dev/test-image:1.0.0"
    t.tags = StringableList([tag])
    return t


def _workflow(target, source_ref=None):
    return PublishWorkflow(image_target=target, oras_bin="oras", soci_bin="soci", source_ref=source_ref)


def _disabled_soci(target):
    return SociOptions(enabled=False)


def _enabled_soci(target):
    return SociOptions(enabled=True)


class TestFullPublishSequence:
    def test_runs_all_phases_in_order_with_soci_disabled(self):
        target = _make_target()
        runner = StubRunner()
        with patch(
            "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
            side_effect=_disabled_soci,
        ):
            result = _workflow(target).run(runner, phases=ALL_PHASES)

        assert result.success is True
        assert result.skipped is False
        assert result.soci_skipped is True
        # create, copy, verify (no soci) — verify produced the verified list
        assert result.verified == ["ghcr.io/posit-dev/test-image:1.0.0"]
        labels = runner.step_labels()
        assert labels == ["index create", "index copy", "verify"]

    def test_soci_enabled_inserts_three_steps_and_propagates_ref(self):
        target = _make_target()
        runner = StubRunner()
        with (
            patch(
                "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
                side_effect=_enabled_soci,
            ),
            patch(
                "posit_bakery.plugins.builtin.imagetools.soci.SociConvertWorkflow._read_converted_digest",
                return_value="sha256:abc",
            ),
        ):
            result = _workflow(target).run(runner, phases=ALL_PHASES)

        assert result.success is True
        assert result.soci_skipped is False
        assert result.soci_destination_ref is not None
        assert result.soci_destination_ref.endswith("-soci")
        labels = runner.step_labels()
        assert labels == ["index create", "soci pull", "soci convert", "soci push", "index copy", "verify"]
        # the index-copy source is the SOCI-converted ref
        copy_cmd = next(c["cmd"] for c in runner.calls if c["step_label"] == "index copy")
        assert any(arg.endswith("-soci") for arg in copy_cmd)


class TestPhaseSubsets:
    def test_merge_phases_skip_soci_and_verify(self):
        target = _make_target()
        runner = StubRunner()
        result = _workflow(target).run(runner, phases=MERGE_PHASES)
        assert result.success is True
        assert runner.step_labels() == ["index create", "index copy"]

    def test_soci_phases_only_convert_from_source_ref(self):
        target = _make_target()
        runner = StubRunner()
        with (
            patch(
                "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
                side_effect=_enabled_soci,
            ),
            patch(
                "posit_bakery.plugins.builtin.imagetools.soci.SociConvertWorkflow._read_converted_digest",
                return_value="sha256:abc",
            ),
        ):
            result = _workflow(target, source_ref="ghcr.io/posit-dev/test-image/tmp:merged").run(
                runner, phases=SOCI_PHASES
            )
        assert result.success is True
        assert runner.step_labels() == ["soci pull", "soci convert", "soci push"]

    def test_soci_phases_disabled_target_is_soci_skipped_not_failed(self):
        target = _make_target()
        runner = StubRunner()
        with patch(
            "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
            side_effect=_disabled_soci,
        ):
            result = _workflow(target, source_ref="ghcr.io/posit-dev/test-image/tmp:merged").run(
                runner, phases=SOCI_PHASES
            )
        assert result.success is True
        assert result.soci_skipped is True
        assert runner.calls == []

    def test_soci_phases_enabled_without_source_ref_is_not_failed(self):
        # Regression (#591 adjacent): a SOCI-enabled target not in this run (no source ref)
        # must be skipped, not reported as a conversion failure.
        target = _make_target()
        runner = StubRunner()
        with patch(
            "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
            side_effect=_enabled_soci,
        ):
            result = _workflow(target, source_ref=None).run(runner, phases=SOCI_PHASES)
        assert result.success is True
        assert result.soci_skipped is True
        assert runner.calls == []


class TestSkipsAndFailures:
    def test_skips_target_without_merge_sources(self):
        target = _make_target(with_merge_sources=False)
        runner = StubRunner()
        result = _workflow(target).run(runner, phases=ALL_PHASES)
        assert result.skipped is True
        assert result.success is True  # a skip is not a failure
        assert runner.calls == []

    def test_missing_temp_registry_is_failure(self):
        target = _make_target()
        target.settings.temp_registry = None
        runner = StubRunner()
        result = _workflow(target).run(runner, phases=ALL_PHASES)
        assert result.success is False
        assert result.failed_phase == "create"

    def test_create_failure_aborts_remaining_phases(self):
        target = _make_target()
        runner = StubRunner(fail_on="manifest index create")
        result = _workflow(target).run(runner, phases=ALL_PHASES)
        assert result.success is False
        assert result.failed_phase == "create"
        # no copy/verify attempted
        assert runner.step_labels() == ["index create"]

    def test_dry_run_skips_verify(self):
        target = _make_target()
        runner = StubRunner()
        with patch(
            "posit_bakery.plugins.builtin.imagetools.soci.get_soci_options_for_target",
            side_effect=_disabled_soci,
        ):
            result = _workflow(target).run(runner, phases=ALL_PHASES, dry_run=True)
        assert result.success is True
        # dry-run short-circuits each command before the runner, so nothing is recorded,
        # and verify is skipped entirely.
        assert result.verified == []


def test_default_phase_set_is_all_four():
    assert ALL_PHASES == frozenset(PublishPhase)
