"""Tests for build.runner module."""

import json
import logging
import shutil
import threading
import time
from pathlib import Path

import pytest

from posit_bakery.build.runner import (
    build_targets,
    BuildResult,
    load_build_metadata_from_file,
    _merge_sequential_build_metadata_files,
)
from posit_bakery.config import BakeryConfig
from posit_bakery.config.settings import BakerySettings
from posit_bakery.error import BakeryBuildErrorGroup, BakeryToolRuntimeError
from posit_bakery.image.image_metadata import BuildMetadata
from posit_bakery.image.image_target import ImageTarget, ImageBuildStrategy
from posit_bakery.settings import SETTINGS
from posit_bakery.targets.selection import select_targets
from test.config.conftest import CONFIG_TESTDATA_DIR

pytestmark = pytest.mark.unit


class TestBuildTargetsBuildStrategy:
    """Tests for build_targets() with ImageBuildStrategy.BUILD."""

    def test_all_targets_built_no_error(self, get_config_obj, mocker):
        config = get_config_obj("basic")
        mocker.patch.object(ImageTarget, "build", lambda self, **kwargs: None)

        result = build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BUILD,
        )

        assert isinstance(result, BuildResult)
        assert result.succeeded_uids is not None

    def test_runs_concurrently_bounded_by_jobs(self, get_config_obj, mocker):
        config = get_config_obj("basic")
        assert len(select_targets(config, config.settings)) >= 2
        lock = threading.Lock()
        active = 0
        max_active = 0

        def fake_build(self, **kwargs):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.1)
            with lock:
                active -= 1
            return None

        mocker.patch.object(ImageTarget, "build", fake_build)

        build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BUILD,
            jobs=2,
        )

        assert max_active >= 2

    def test_single_failure_raised_directly(self, get_config_obj, mocker):
        config = get_config_obj("basic")
        failing_uid = select_targets(config, config.settings)[0].uid

        def fake_build(self, **kwargs):
            if self.uid == failing_uid:
                raise BakeryToolRuntimeError("boom", cmd=["docker", "build"])
            return None

        mocker.patch.object(ImageTarget, "build", fake_build)

        with pytest.raises(BakeryToolRuntimeError):
            build_targets(
                base_path=config.base_path,
                targets=select_targets(config, config.settings),
                temp_registry=config.settings.temp_registry,
                clean_temporary=config.settings.clean_temporary,
                strategy=ImageBuildStrategy.BUILD,
            )

    def test_multiple_failures_raised_as_error_group(self, get_config_obj, mocker):
        config = get_config_obj("basic")
        assert len(select_targets(config, config.settings)) >= 2

        def fake_build(self, **kwargs):
            raise BakeryToolRuntimeError("boom", cmd=["docker", "build"])

        mocker.patch.object(ImageTarget, "build", fake_build)

        with pytest.raises(BakeryBuildErrorGroup):
            build_targets(
                base_path=config.base_path,
                targets=select_targets(config, config.settings),
                temp_registry=config.settings.temp_registry,
                clean_temporary=config.settings.clean_temporary,
                strategy=ImageBuildStrategy.BUILD,
            )

    def test_fail_fast_stops_unstarted_targets(self, get_config_obj, mocker):
        config = get_config_obj("basic")
        assert len(select_targets(config, config.settings)) >= 2
        failing_uid = select_targets(config, config.settings)[0].uid
        called_uids = []

        def fake_build(self, **kwargs):
            called_uids.append(self.uid)
            if self.uid == failing_uid:
                raise BakeryToolRuntimeError("boom", cmd=["docker", "build"])
            return None

        mocker.patch.object(ImageTarget, "build", fake_build)

        # jobs=1 fully serializes the two targets, so the second must never start
        # once the first (and only) job fails with fail_fast set.
        with pytest.raises(BakeryToolRuntimeError):
            build_targets(
                base_path=config.base_path,
                targets=select_targets(config, config.settings),
                temp_registry=config.settings.temp_registry,
                clean_temporary=config.settings.clean_temporary,
                strategy=ImageBuildStrategy.BUILD,
                fail_fast=True,
                jobs=1,
            )

        assert called_uids == [failing_uid]

    def test_metadata_file_written(self, get_config_obj, mocker, tmp_path):
        config = get_config_obj("basic")
        metadata_path = tmp_path / "metadata.json"
        mocker.patch.object(ImageTarget, "build", lambda self, **kwargs: None)

        build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BUILD,
            metadata_file=metadata_path,
        )

        assert metadata_path.is_file()

    def test_real_build_streams_through_prefixed_log_sink(self, get_config_obj, mocker, capsys):
        """Exercises the real BUILD-branch wiring end to end: ImageTarget.build() is NOT
        mocked, only python_on_whales.docker.build() at the tool boundary, so the closure
        `build_targets()` constructs (streaming build() output into a real PrefixedLogSink)
        actually runs. Regression test for the Task 1 + Task 2 + Task 4 integration seam.
        """
        config = get_config_obj("basic")
        assert len(select_targets(config, config.settings)) >= 2
        fake_lines = ["Step 1/2 : FROM ubuntu", "Step 2/2 : RUN true"]
        mocker.patch("python_on_whales.docker.build", side_effect=lambda **kwargs: iter(fake_lines))

        build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BUILD,
        )

        output = capsys.readouterr().err
        for target in select_targets(config, config.settings):
            assert target.uid in output
        assert fake_lines[0] in output

    def test_quiet_mode_skips_log_streaming(self, get_config_obj, mocker):
        """Under -q (SETTINGS.log_level == ERROR), log_callback must not be wired up --
        otherwise ImageTarget.build() forces docker's "plain" progress and streams output
        the user asked to suppress.
        """
        config = get_config_obj("basic")
        original_log_level = SETTINGS.log_level
        SETTINGS.log_level = logging.ERROR
        try:
            captured_kwargs = []
            mocker.patch.object(ImageTarget, "build", lambda self, **kwargs: captured_kwargs.append(kwargs))
            build_targets(
                base_path=config.base_path,
                targets=select_targets(config, config.settings),
                temp_registry=config.settings.temp_registry,
                clean_temporary=config.settings.clean_temporary,
                strategy=ImageBuildStrategy.BUILD,
            )
        finally:
            SETTINGS.log_level = original_log_level

        assert captured_kwargs
        assert all(kwargs["log_callback"] is None for kwargs in captured_kwargs)

    def test_retry_backoff_uses_interruptible_runner_sleep(self, get_config_obj, mocker):
        """_retry_build's backoff must go through CommandRunner.sleep (interruptible via
        ExecutorInterrupted when the executor is shutting down), not a bare time.sleep --
        otherwise a queued retry can't be woken by a shutdown request and blocks the full
        delay.
        """
        config = get_config_obj("basic")
        failing_uid = select_targets(config, config.settings)[0].uid
        attempted = {"done": False}

        def fake_build(self, **kwargs):
            if self.uid == failing_uid and not attempted["done"]:
                attempted["done"] = True
                raise BakeryToolRuntimeError("boom", cmd=["docker", "build"])
            return None

        mocker.patch.object(ImageTarget, "build", fake_build)
        mock_time_sleep = mocker.patch("posit_bakery.build.runner.time.sleep")
        spy_runner_sleep = mocker.patch("posit_bakery.parallel.executor.CommandRunner.sleep", autospec=True)

        build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BUILD,
            retry=1,
        )

        spy_runner_sleep.assert_called_once()
        mock_time_sleep.assert_not_called()

    def test_succeeded_uids_set_on_full_success(self, get_config_obj, mocker):
        config = get_config_obj("basic")
        mocker.patch.object(ImageTarget, "build", lambda self, **kwargs: None)

        result = build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BUILD,
        )

        assert result.succeeded_uids == {t.uid for t in select_targets(config, config.settings)}

    def test_succeeded_uids_excludes_the_target_that_failed(self, get_config_obj, mocker):
        """Set before the raise, not after -- --summary needs it even on a failed build."""
        config = get_config_obj("basic")
        targets = select_targets(config, config.settings)
        assert len(targets) >= 2
        failing_uid = targets[0].uid

        def fake_build(self, **kwargs):
            if self.uid == failing_uid:
                raise BakeryToolRuntimeError("boom", cmd=["docker", "build"])
            return None

        mocker.patch.object(ImageTarget, "build", fake_build)

        with pytest.raises(BakeryToolRuntimeError) as exc_info:
            build_targets(
                base_path=config.base_path,
                targets=targets,
                temp_registry=config.settings.temp_registry,
                clean_temporary=config.settings.clean_temporary,
                strategy=ImageBuildStrategy.BUILD,
            )

        assert exc_info.value.build_result.succeeded_uids == {t.uid for t in targets if t.uid != failing_uid}


class TestBuildTargetsBakeStrategy:
    """Tests for build_targets() with ImageBuildStrategy.BAKE."""

    def test_metadata_file_forwarded_to_bake_plan(self, get_config_obj, mocker):
        """metadata_file must be forwarded to BakePlan.build() so it reaches
        `docker buildx bake --metadata-file`."""
        config = get_config_obj("basic")
        metadata_path = Path("/tmp/does-not-matter.json")
        mock_build = mocker.patch("posit_bakery.image.bake.BakePlan.build")
        mocker.patch("posit_bakery.build.runner.load_build_metadata_from_file")

        build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BAKE,
            metadata_file=metadata_path,
        )

        mock_build.assert_called_once()
        assert mock_build.call_args.kwargs["metadata_file"] == metadata_path

    def test_temp_registry_push_disables_provenance(self, get_config_file, mocker):
        config = BakeryConfig(get_config_file("basic"), BakerySettings(temp_registry="registry.example.com"))
        mock_build = mocker.patch("posit_bakery.image.bake.BakePlan.build")

        build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BAKE,
            push=True,
        )

        assert mock_build.call_args.kwargs["set_opts"] == {
            "*.output": {"type": "image", "push-by-digest": True, "name-canonical": True, "push": True},
            "*.attest": "type=provenance,disabled=true",
        }

    def test_no_metadata_file_by_default(self, get_config_obj, mocker):
        """When metadata_file is not given, None must be forwarded and no metadata load attempted."""
        config = get_config_obj("basic")
        mock_build = mocker.patch("posit_bakery.image.bake.BakePlan.build")
        mock_load = mocker.patch("posit_bakery.build.runner.load_build_metadata_from_file")

        build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BAKE,
        )

        assert mock_build.call_args.kwargs["metadata_file"] is None
        mock_load.assert_not_called()

    def test_metadata_loaded_back_into_targets(self, get_config_obj, mocker, tmp_path):
        """After a successful bake with a metadata_file, the resulting file (written by
        `docker buildx bake --metadata-file`, keyed by bake target/UID) must be loaded back
        into each target's build_metadata, mirroring the BUILD strategy's behavior."""
        config = get_config_obj("basic")
        metadata_path = tmp_path / "metadata.json"

        expected_metadata_path = CONFIG_TESTDATA_DIR / "build_metadata" / "expected.json"
        shutil.copyfile(expected_metadata_path, metadata_path)

        mocker.patch("posit_bakery.image.bake.BakePlan.build")
        # select_targets returns new objects per call; reuse one list to observe mutation
        targets = select_targets(config, config.settings)

        build_targets(
            base_path=config.base_path,
            targets=targets,
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BAKE,
            metadata_file=metadata_path,
        )

        # Ensure all targets now have build metadata loaded
        for target in targets:
            assert len(target.build_metadata) > 0

    def test_bake_returns_none_succeeded_uids(self, get_config_obj, mocker):
        """BAKE strategy has no per-target result tracking, so succeeded_uids should be None."""
        config = get_config_obj("basic")
        mocker.patch("posit_bakery.image.bake.BakePlan.build")

        result = build_targets(
            base_path=config.base_path,
            targets=select_targets(config, config.settings),
            temp_registry=config.settings.temp_registry,
            clean_temporary=config.settings.clean_temporary,
            strategy=ImageBuildStrategy.BAKE,
        )

        assert isinstance(result, BuildResult)
        assert result.succeeded_uids is None


class TestMetadataFunctions:
    """Tests for metadata loading and merging functions."""

    def test_merge_sequential_build_metadata_files(self, get_config_obj):
        """Test merging sequential build metadata files."""
        config = get_config_obj("basic")
        targets = select_targets(config, config.settings)
        for target in targets:
            metadata_filepath = CONFIG_TESTDATA_DIR / "build_metadata" / f"{target.uid}.json"
            target.build_metadata.append(BuildMetadata.model_validate_json(metadata_filepath.read_text()))

        merged_metadata = _merge_sequential_build_metadata_files(targets)
        with open(CONFIG_TESTDATA_DIR / "build_metadata" / "expected.json", "r") as f:
            expected_metadata = json.load(f)

        assert merged_metadata == expected_metadata

    def test_load_build_metadata_file(self, get_config_obj):
        """Test loading a build metadata file."""
        metadata_filepath = CONFIG_TESTDATA_DIR / "build_metadata" / "expected.json"
        config = get_config_obj("basic")
        targets = select_targets(config, config.settings)
        load_build_metadata_from_file(targets, metadata_filepath)

        for target in targets:
            assert len(target.build_metadata) == 1
            assert target.build_metadata[0] is not None
            assert target.build_metadata[0].image_name is not None
            assert target.build_metadata[0].container_image_digest is not None
