import json
import logging
import time
from pathlib import Path

from python_on_whales import DockerException

from posit_bakery.error import BakeryBuildErrorGroup, BakeryFileError, BakeryToolRuntimeError
from posit_bakery.image.bake.bake import BakePlan
from posit_bakery.image.image_target import ImageTarget, ImageBuildStrategy

log = logging.getLogger(__name__)

_RETRY_DELAY_SECONDS = 5


def _retry_build(fn, retry: int, label: str) -> None:
    """Attempt fn() up to (retry + 1) times, re-raising on final failure."""
    for attempt in range(retry + 1):
        try:
            fn()
            return
        except BakeryFileError:
            raise
        except (DockerException, BakeryToolRuntimeError) as e:
            if attempt < retry:
                log.warning(
                    f"Build failed for '{label}' (attempt {attempt + 1}/{retry + 1}). "
                    f"Retrying in {_RETRY_DELAY_SECONDS}s..."
                )
                time.sleep(_RETRY_DELAY_SECONDS)
            else:
                raise e


def build_targets(
    targets: list[ImageTarget],
    base_path: Path,
    load: bool = True,
    push: bool = False,
    pull: bool = False,
    cache: bool = True,
    platforms: list[str] | None = None,
    strategy: ImageBuildStrategy = ImageBuildStrategy.BAKE,
    metadata_file: Path | None = None,
    fail_fast: bool = False,
    retry: int = 0,
    temp_registry: str | None = None,
    clean_temporary: bool = True,
):
    """Build image targets using the specified strategy.

    :param targets: Image targets to build.
    :param base_path: Root path of the bakery project.
    :param load: If True, load the built images into the local Docker daemon.
    :param push: If True, push the built images to the configured registries.
    :param pull: If True, always pull the latest version of base images.
    :param cache: If True, use the build cache when building images.
    :param platforms: Optional list of platforms to build for.
    :param strategy: The strategy to use when building images.
    :param metadata_file: Optional path to a metadata file to write build metadata to.
    :param fail_fast: If True, stop building targets on the first failure.
    :param retry: Number of times to retry a failed build (default 0, no retries).
    :param temp_registry: Temporary registry for push-by-digest builds.
    :param clean_temporary: If True, clean up temporary bake files after building.
    """
    if strategy == ImageBuildStrategy.BAKE:
        bake_plan = BakePlan.from_image_targets(
            context=base_path, image_targets=targets, platforms=platforms, push=push
        )
        set_opts = None
        if temp_registry is not None and push:
            set_opts = {"*.output": {"type": "image", "push-by-digest": True, "name-canonical": True, "push": True}}
        _retry_build(
            lambda: bake_plan.build(
                load=load,
                push=push,
                pull=pull,
                cache=cache,
                clean_bakefile=clean_temporary,
                platforms=platforms,
                set_opts=set_opts,
            ),
            retry=retry,
            label="bake plan",
        )
    elif strategy == ImageBuildStrategy.BUILD:
        errors: list[Exception] = []
        for target in targets:
            try:
                _retry_build(
                    lambda t=target: t.build(
                        load=load,
                        push=push,
                        pull=pull,
                        cache=cache,
                        platforms=platforms,
                        metadata_file=True if metadata_file else False,
                    ),
                    retry=retry,
                    label=str(target),
                )
            except (BakeryFileError, DockerException, BakeryToolRuntimeError) as e:
                log.error(f"Failed to build image target '{str(target)}'.")
                if fail_fast:
                    log.info("--fail-fast is set, stopping builds...")
                    raise e
                errors.append(e)
        if errors:
            if len(errors) == 1:
                raise errors[0]
            raise BakeryBuildErrorGroup("Multiple errors occurred while building images.", errors)
        if metadata_file is not None:
            merged_metadata: dict = {}
            for target in targets:
                for build_metadata in target.build_metadata:
                    merged_metadata[target.uid] = build_metadata.model_dump(exclude_none=True, by_alias=True)
            with open(metadata_file, "w") as f:
                log.info(f"Writing build metadata to '{str(metadata_file)}'.")
                json.dump(merged_metadata, f, indent=2)
