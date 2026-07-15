"""Tests for ImageToolsPlugin's per-target publish Stage 1 helper (wait + create + soci)."""

from unittest.mock import MagicMock, patch

import pytest

from posit_bakery.error import BakeryToolRuntimeError
from posit_bakery.plugins.builtin.imagetools.imagetools import _PublishStage1Result, _run_publish_stage1

pytestmark = [pytest.mark.unit]


def _target(uid="uid1", merge_sources=None, temp_registry="ghcr.io/posit-dev"):
    t = MagicMock()
    t.uid = uid
    t.get_merge_sources.return_value = merge_sources if merge_sources is not None else ["ghcr.io/x@sha256:a"]
    t.settings.temp_registry = temp_registry
    t.labels = {}
    # No real SociOptions configured anywhere -> get_soci_options_for_target resolves to
    # a disabled default without needing to iterate real option lists.
    t.image_version.parent.options = []
    t.image_variant = None
    return t


def _wait_ok(sources):
    return MagicMock(success=True, ready=sources, missing=[], waited_seconds=0.1, error=None)


def _wait_fail(sources):
    return MagicMock(success=False, ready=[], missing=sources, waited_seconds=600.0, error="still unreadable")


class TestRunPublishStage1:
    def test_skips_target_with_no_merge_sources(self):
        target = _target(merge_sources=[])
        result = _run_publish_stage1(target, "oras", "soci", dry_run=False)
        assert result.skipped is True
        assert result.skip_reason == "no merge sources"

    def test_fails_when_temp_registry_not_configured(self):
        target = _target(temp_registry=None)
        result = _run_publish_stage1(target, "oras", "soci", dry_run=False)
        assert result.success is False
        assert result.failed_phase == "create"

    def test_success_without_soci(self):
        target = _target()
        with (
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
                return_value=MagicMock(run=MagicMock(return_value=_wait_ok(target.get_merge_sources()))),
            ),
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow",
                return_value=MagicMock(
                    run=MagicMock(return_value=MagicMock(success=True, temp_ref="ghcr.io/x/tmp:created"))
                ),
            ),
        ):
            result = _run_publish_stage1(target, "oras", "soci", dry_run=False)

        assert result.success is True
        assert result.skipped is False
        assert result.temp_ref == "ghcr.io/x/tmp:created"

    def test_wait_failure_marks_target_failed(self):
        target = _target()
        with patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
            return_value=MagicMock(run=MagicMock(return_value=_wait_fail(target.get_merge_sources()))),
        ):
            result = _run_publish_stage1(target, "oras", "soci", dry_run=False)

        assert result.success is False
        assert result.failed_phase == "wait"

    def test_non_transient_wait_error_marks_target_failed_not_raised(self):
        target = _target()
        error = BakeryToolRuntimeError(
            message="oras command failed",
            tool_name="oras",
            cmd=["oras", "manifest", "fetch"],
            stdout=b"",
            stderr=b"unauthorized: authentication required",
        )
        with patch(
            "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
            return_value=MagicMock(run=MagicMock(side_effect=error)),
        ):
            result = _run_publish_stage1(target, "oras", "soci", dry_run=False)

        assert result.success is False
        assert result.failed_phase == "wait"

    def test_create_failure_marks_target_failed(self):
        target = _target()
        with (
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
                return_value=MagicMock(run=MagicMock(return_value=_wait_ok(target.get_merge_sources()))),
            ),
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow",
                return_value=MagicMock(
                    run=MagicMock(return_value=MagicMock(success=False, temp_ref=None, error="boom"))
                ),
            ),
        ):
            result = _run_publish_stage1(target, "oras", "soci", dry_run=False)

        assert result.success is False
        assert result.failed_phase == "create"
        assert result.error == "boom"

    def test_soci_enabled_success_overwrites_temp_ref(self):
        target = _target()
        from posit_bakery.plugins.builtin.imagetools.options import SociOptions

        target.image_version.parent.options = [SociOptions(enabled=True)]
        with (
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
                return_value=MagicMock(run=MagicMock(return_value=_wait_ok(target.get_merge_sources()))),
            ),
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow",
                return_value=MagicMock(
                    run=MagicMock(return_value=MagicMock(success=True, temp_ref="ghcr.io/x/tmp:created"))
                ),
            ),
            patch(
                "posit_bakery.plugins.builtin.imagetools.soci.SociConvertWorkflow",
                return_value=MagicMock(
                    run=MagicMock(return_value=MagicMock(success=True, destination_ref="ghcr.io/x/tmp:created-soci"))
                ),
            ),
        ):
            result = _run_publish_stage1(target, "oras", "soci", dry_run=False)

        assert result.success is True
        assert result.temp_ref == "ghcr.io/x/tmp:created-soci"

    def test_soci_failure_marks_target_failed(self):
        target = _target()
        from posit_bakery.plugins.builtin.imagetools.options import SociOptions

        target.image_version.parent.options = [SociOptions(enabled=True)]
        with (
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
                return_value=MagicMock(run=MagicMock(return_value=_wait_ok(target.get_merge_sources()))),
            ),
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow",
                return_value=MagicMock(
                    run=MagicMock(return_value=MagicMock(success=True, temp_ref="ghcr.io/x/tmp:created"))
                ),
            ),
            patch(
                "posit_bakery.plugins.builtin.imagetools.soci.SociConvertWorkflow",
                return_value=MagicMock(
                    run=MagicMock(return_value=MagicMock(success=False, destination_ref=None, error="soci boom"))
                ),
            ),
        ):
            result = _run_publish_stage1(target, "oras", "soci", dry_run=False)

        assert result.success is False
        assert result.failed_phase == "soci"
        assert result.error == "soci boom"

    def test_passes_runner_through_to_wait_and_create(self):
        target = _target()
        fake_runner = MagicMock()
        with (
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasWaitForSourcesWorkflow",
                return_value=MagicMock(run=MagicMock(return_value=_wait_ok(target.get_merge_sources()))),
            ) as wait_ctor,
            patch(
                "posit_bakery.plugins.builtin.imagetools.oras.OrasIndexCreateWorkflow",
                return_value=MagicMock(
                    run=MagicMock(return_value=MagicMock(success=True, temp_ref="ghcr.io/x/tmp:created"))
                ),
            ) as create_ctor,
        ):
            _run_publish_stage1(target, "oras", "soci", dry_run=False, runner=fake_runner)

        wait_ctor.return_value.run.assert_called_once_with(dry_run=False, runner=fake_runner)
        create_ctor.return_value.run.assert_called_once_with(dry_run=False, runner=fake_runner)
