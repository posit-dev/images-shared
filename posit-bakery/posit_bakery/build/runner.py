"""Build execution orchestration for image targets."""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Any

from python_on_whales import DockerException

from posit_bakery.error import (
    BakeryFileError,
    BakeryToolRuntimeError,
    BakeryBuildErrorGroup,
)
from posit_bakery.image.bake.bake import BakePlan
from posit_bakery.image.image_metadata import MetadataFile
from posit_bakery.image.image_target import ImageTarget, ImageBuildStrategy
from posit_bakery.parallel import ParallelShellExecutor, PrefixedLogSink, ShellJob, resolve_max_workers
from posit_bakery.settings import SETTINGS

log = logging.getLogger(__name__)

_RETRY_DELAY_SECONDS = 5


@dataclass
class BuildResult:
    """Result from building image targets.

    Attributes:
        succeeded_uids: Set of target UIDs that succeeded in the build, or None if the
            build strategy does not track per-target results (e.g., BAKE strategy).
    """

    succeeded_uids: set[str] | None


def _retry_build(fn, retry: int, label: str, sleep: Callable[[float], None] | None = None) -> None:
    """Attempt fn() up to (retry + 1) times, re-raising on final failure.

    :param fn: The function to call.
    :param retry: Number of retries (0 means no retries, just one attempt).
    :param label: A label for logging purposes.
    :param sleep: Sleep function used between retry attempts. When omitted (``None``),
        ``time.sleep`` is looked up fresh on each call rather than bound as a parameter
        default, so tests that ``patch("posit_bakery.build.runner.time.sleep")`` keep
        working. Pass ``CommandRunner.sleep`` when retrying inside a parallel job so
        backoff waits notice a shutdown request promptly instead of blocking process exit.
    """
    effective_sleep = sleep if sleep is not None else time.sleep
    for attempt in range(retry + 1):
        try:
            fn()
            return
        except BakeryFileError:
            raise  # Never retry file errors
        except (DockerException, BakeryToolRuntimeError):
            if attempt < retry:
                log.warning(
                    f"Build failed for '{label}' (attempt {attempt + 1}/{retry + 1}). "
                    f"Retrying in {_RETRY_DELAY_SECONDS}s..."
                )
                effective_sleep(_RETRY_DELAY_SECONDS)
            else:
                raise


def load_build_metadata_from_file(targets: list[ImageTarget], metadata_file: Path) -> list[str]:
    """Loads build metadata from a given metadata file.

    :param targets: List of ImageTarget objects to load metadata for.
    :param metadata_file: Path to the metadata file to load.
    :return: A list of target UIDs loaded.
    """
    metadata_file_obj = MetadataFile.load(metadata_file)

    targets_loaded = []
    for target in targets:
        result = target.load_build_metadata_from_file(metadata_file_obj)
        if result is not None:
            targets_loaded.append(target.uid)
            log.info(f"Loaded build metadata for target '{target}' from file '{metadata_file_obj.filepath}'.")

    return targets_loaded


def _merge_sequential_build_metadata_files(targets: list[ImageTarget]) -> dict[str, Any]:
    """Merges all sequential build metadata files generated during image builds.

    :param targets: List of ImageTarget objects to merge metadata from.
    :return: A dictionary containing the merged metadata.
    """
    merged_metadata: dict[str, dict[str, Any]] = {}
    for target in targets:
        for build_metadata in target.build_metadata:
            merged_metadata[target.uid] = build_metadata.model_dump(exclude_none=True, by_alias=True)

    return merged_metadata


def bake_plan_json(base_path: Path, targets: list[ImageTarget], push: bool = False) -> str:
    """Generates a bake plan JSON string for the given image targets.

    :param base_path: The base path for the bakery project (parent of bakery.yaml).
    :param targets: List of ImageTarget objects to include in the bake plan.
    :param push: When True, include cache-to exports in the bake plan so that
        cache layers are written to the registry alongside the built images.
    :return: JSON string representation of the bake plan.
    """
    bake_plan = BakePlan.from_image_targets(context=base_path, image_targets=targets, push=push)
    return bake_plan.model_dump_json(indent=2, exclude_none=True, by_alias=True)


def build_targets(
    base_path: Path,
    targets: list[ImageTarget],
    temp_registry: str | None,
    clean_temporary: bool,
    load: bool = True,
    push: bool = False,
    pull: bool = False,
    cache: bool = True,
    platforms: list[str] | None = None,
    strategy: ImageBuildStrategy = ImageBuildStrategy.BAKE,
    metadata_file: Path | None = None,
    fail_fast: bool = False,
    retry: int = 0,
    jobs: int | None = None,
) -> BuildResult:
    """Build image targets using the specified strategy.

    :param base_path: The base path for the bakery project (parent of bakery.yaml).
    :param targets: List of ImageTarget objects to build.
    :param temp_registry: Optional temporary registry for pushing intermediate images.
    :param clean_temporary: Whether to clean up temporary files after the build.
    :param load: If True, load the built images into the local Docker daemon.
    :param push: If True, push the built images to the configured registries.
    :param pull: If True, always pull the latest version of base images.
    :param cache: If True, use the build cache when building images.
    :param platforms: Optional list of platforms to build for. If None, builds for the configuration specified
        platform.
    :param strategy: The strategy to use when building images.
    :param metadata_file: Optional path to a metadata file to write build metadata to.
    :param fail_fast: If True, stop building targets on the first failure. Only affects
        targets whose build has not yet started; already-running builds finish.
    :param retry: Number of times to retry a failed build (default 0, no retries).
    :param jobs: Maximum number of targets to build concurrently for `--strategy build`
        (ignored for `--strategy bake`, which manages its own parallelism). Falls back to
        `SETTINGS.max_concurrency` when not given.
    :return: BuildResult with succeeded_uids set for BUILD strategy, None for BAKE strategy.
    """
    if strategy == ImageBuildStrategy.BAKE:
        bake_plan = BakePlan.from_image_targets(
            context=base_path, image_targets=targets, platforms=platforms, push=push
        )
        set_opts = None
        if temp_registry is not None and push:
            set_opts = {
                "*.output": {"type": "image", "push-by-digest": True, "name-canonical": True, "push": True},
                "*.attest": "type=provenance,disabled=true",
            }
        _retry_build(
            lambda: bake_plan.build(
                load=load,
                push=push,
                pull=pull,
                cache=cache,
                clean_bakefile=clean_temporary,
                platforms=platforms,
                set_opts=set_opts,
                metadata_file=metadata_file,
            ),
            retry=retry,
            label="bake plan",
        )
        if metadata_file is not None:
            load_build_metadata_from_file(targets, metadata_file)
        return BuildResult(succeeded_uids=None)
    elif strategy == ImageBuildStrategy.BUILD:
        sink = PrefixedLogSink()
        # Mirrors ImageTarget.build()'s own quiet check: streaming is pointless (and
        # forces docker's "plain" progress mode) when -q means the lines are discarded.
        quiet = SETTINGS.log_level >= logging.ERROR
        shell_jobs = [
            ShellJob(
                key=target.uid,
                label=str(target),
                run=lambda runner, t=target: _retry_build(
                    lambda: t.build(
                        load=load,
                        push=push,
                        pull=pull,
                        cache=cache,
                        platforms=platforms,
                        metadata_file=True if metadata_file else None,
                        log_callback=None if quiet else (lambda line, u=t.uid: sink.write(u, line)),
                    ),
                    retry=retry,
                    label=str(t),
                    # python_on_whales owns the build subprocess and doesn't expose its Popen
                    # (utils.py), so a mid-build target can't be cancelled -- only the
                    # inter-attempt backoff can. Routing it through runner.sleep lets
                    # --fail-fast/shutdown interrupt a queued retry instead of blocking on it.
                    sleep=runner.sleep,
                ),
            )
            for target in targets
        ]
        executor = ParallelShellExecutor(max_workers=resolve_max_workers(jobs, len(shell_jobs)), use_live=False)
        job_results = executor.run_jobs(shell_jobs, fail_fast=fail_fast)
        succeeded_uids = {jr.job.key for jr in job_results if jr.ok}

        errors: list[Exception] = []
        for jr in job_results:
            if not jr.ok:
                log.error(f"Failed to build image target '{jr.job.display_label}'.")
                errors.append(jr.exception)
        if fail_fast and errors:
            log.info("--fail-fast is set, stopping builds...")
        build_result = BuildResult(succeeded_uids=succeeded_uids)
        if errors:
            error = (
                errors[0]
                if len(errors) == 1
                else BakeryBuildErrorGroup("Multiple errors occurred while building images.", errors)
            )
            # Preserve partial results for callers that need to report only artifacts
            # produced by this invocation, even when the build itself fails.
            setattr(error, "build_result", build_result)
            raise error
        if metadata_file is not None:
            with open(metadata_file, "w") as f:
                log.info(f"Writing build metadata to '{str(metadata_file)}'.")
                json.dump(_merge_sequential_build_metadata_files(targets), f, indent=2)

        return build_result
