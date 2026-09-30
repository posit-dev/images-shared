"""Target selection logic for Bakery builds.

Extracted from config/config.py to separate target filtering from config
loading and validation.
"""

import logging
import re
from typing import TYPE_CHECKING

import typer

from posit_bakery.config.image.parsed_version import version_matches, version_sort_key
from posit_bakery.config.settings import BakerySettings
from posit_bakery.const import DevVersionInclusionEnum, MatrixVersionInclusionEnum
from posit_bakery.error import BakeryError
from posit_bakery.image.image_target import ImageTarget, ImageTargetSettings
from posit_bakery.log import stderr_console

if TYPE_CHECKING:
    from posit_bakery.config.config import BakeryConfig
    from posit_bakery.config.image import ImageVersion

log = logging.getLogger(__name__)


def apply_recent_versions(
    versions: list["ImageVersion"],
    count: int,
    image_name: str,
    image_version_filter: str | None = None,
) -> list["ImageVersion"]:
    """Limit release candidates to the highest-sorted versions.

    Development versions are exempt from the limit. Warn when an excluded
    release version explicitly matches ``--image-version`` so a named build is
    never silently skipped.
    """
    release_versions = [version for version in versions if not version.isDevelopmentVersion]
    dev_versions = [version for version in versions if version.isDevelopmentVersion]

    release_versions.sort(key=version_sort_key, reverse=True)
    excluded_versions = release_versions[count:]
    if image_version_filter is not None:
        for version in excluded_versions:
            if version_matches(version.name, image_version_filter):
                log.warning(
                    f"Version '{version.name}' in image '{image_name}' matches --image-version filter "
                    f"but is being skipped: excluded by --recent {count}"
                )
    return release_versions[:count] + dev_versions


def select_targets(config: "BakeryConfig", settings: BakerySettings, *, sort: bool = True) -> list[ImageTarget]:
    """Generate image targets from the config, applying filters from settings.

    :param config: The BakeryConfig instance containing loaded images.
    :param settings: Settings to apply when generating image targets.
    :param sort: When True, sort targets by their string form. When False, keep
        generation order: images and versions as listed in bakery.yaml (dev
        versions after releases), then variants and OSes.
    :return: List of ImageTarget objects matching the filters.
    """
    targets: list[ImageTarget] = []
    for image in config.model.images:
        if settings.filter.image_name is not None and re.search(settings.filter.image_name, image.name) is None:
            log.debug(f"Skipping image '{image.name}' due to not matching name filter '{settings.filter.image_name}'")
            continue
        versions = list(image.versions)
        image_name_filter_matched = settings.filter.image_name is not None and re.search(
            settings.filter.image_name, image.name
        )
        if (image.matrix is None and settings.matrix_versions == MatrixVersionInclusionEnum.ONLY) or (
            image.matrix is not None and settings.matrix_versions == MatrixVersionInclusionEnum.EXCLUDE
        ):
            if image_name_filter_matched:
                reason = (
                    "matrix image excluded by default (use --matrix-versions include)"
                    if image.matrix is not None
                    else "non-matrix image excluded by --matrix-versions only"
                )
                log.warning(f"Image '{image.name}' matches --image-name filter but is being skipped: {reason}")
            continue
        elif image.matrix is not None and settings.matrix_versions != MatrixVersionInclusionEnum.EXCLUDE:
            if settings.dev_versions == DevVersionInclusionEnum.ONLY:
                # Dev versions are already in image.versions (from load_dev_versions()).
                # Matrix production versions (isDevelopmentVersion=False) would all be
                # filtered out by --dev-versions only, so there is nothing to merge.
                pass
            elif settings.dev_versions == DevVersionInclusionEnum.INCLUDE:
                dev_versions_loaded = [v for v in image.versions if v.isDevelopmentVersion]
                versions = image.matrix.to_image_versions() + dev_versions_loaded
            else:
                versions = image.matrix.to_image_versions()
        elif image.matrix is None and settings.recent is not None:
            versions = apply_recent_versions(
                versions,
                settings.recent,
                image.name,
                settings.filter.image_version,
            )
        targets_before = len(targets)
        for version in versions:
            version_filter_matched = settings.filter.image_version is not None and version_matches(
                version.name, settings.filter.image_version
            )
            included, reason = version.matches_dev_filter(settings.dev_versions, settings.effective_dev_channel)
            if not included:
                if version_filter_matched:
                    log.warning(
                        f"Version '{version.name}' in image '{image.name}' matches --image-version filter "
                        f"but is being skipped: {reason}"
                    )
                else:
                    log.debug(f"Skipping version '{version.name}' in image '{image.name}': {reason}")
                continue
            if settings.filter.image_version is not None and not version_matches(
                version.name, settings.filter.image_version
            ):
                log.debug(
                    f"Skipping image version '{version.name}' in image '{image.name}' "
                    f"due to not matching version filter '{settings.filter.image_version}'"
                )
                continue
            included, reason = version.matches_latest_filter(settings.latest)
            if not included:
                if version_filter_matched:
                    log.warning(
                        f"Version '{version.name}' in image '{image.name}' matches --image-version filter "
                        f"but is being skipped: {reason}"
                    )
                else:
                    log.debug(f"Skipping version '{version.name}' in image '{image.name}': {reason}")
                continue
            for variant in image.variants or [None]:
                if (
                    settings.filter.image_variant is not None
                    and re.search(settings.filter.image_variant, variant.name) is None
                ):
                    log.debug(
                        f"Skipping image variant '{variant.name}' in image '{image.name}' "
                        f"due to not matching variant filter '{settings.filter.image_variant}'"
                    )
                    continue
                for _os in version.os or [None]:
                    if settings.filter.image_os is not None and _os is None:
                        log.warning(
                            f"Image '{image.name}' version '{version.name}' has no OS defined but --image-os "
                            "filter is set. --image-os filter will be ignored for this image version."
                        )
                    elif settings.filter.image_os is not None and re.search(settings.filter.image_os, _os.name) is None:
                        log.debug(
                            f"Skipping image OS '{_os.name}' in image '{image.name}' "
                            f"due to not matching OS filter '{settings.filter.image_os}'"
                        )
                        continue
                    if settings.filter.image_platform and _os is None:
                        log.warning(
                            f"Image '{image.name}' version '{version.name}' has no OS defined but --image-platform "
                            "filter is set. --image-platform filter will be ignored for this image version."
                        )
                    elif settings.filter.image_platform and all(
                        re.search(filter_platform, platform) is None
                        for platform in _os.platforms
                        for filter_platform in settings.filter.image_platform
                    ):
                        log.debug(
                            f"Skipping image '{image.name}' "
                            f"due to no matching platforms for patterns {settings.filter.image_platform}, "
                            f"supported platforms are: {', '.join(_os.platforms)}"
                        )
                        continue
                    targets.append(
                        ImageTarget.new_image_target(
                            repository=config.model.repository,
                            image_version=version,
                            image_variant=variant,
                            image_os=_os,
                            settings=ImageTargetSettings(
                                temp_registry=settings.temp_registry, cache_registry=settings.cache_registry
                            ),
                        )
                    )
        if image_name_filter_matched and len(targets) == targets_before:
            log.warning(
                f"Image '{image.name}' matches --image-name filter but yielded no targets after applying "
                f"other filters (--image-version, --image-variant, --image-os, --image-platform, --dev-versions)"
            )

    if sort:
        targets = sorted(targets, key=lambda t: str(t))

    # Build metadata is matched to targets by UID, so a duplicate would let one
    # build's artifacts be pushed as another's. Fail fast.
    seen: dict[str, ImageTarget] = {}
    for target in targets:
        if target.uid in seen:
            raise BakeryError(
                f"Duplicate image target UID '{target.uid}': two targets resolve to the same "
                f"image, version, variant, OS, and release channel ({target.release_channel.value}). "
                "Check for a duplicate version definition or multiple development channels "
                "resolving to the same version."
            )
        seen[target.uid] = target

    return targets


def exit_if_no_targets(targets: list[ImageTarget], settings: BakerySettings, context: str = "build") -> None:
    """Abort the command when the active filters resolved to zero image targets.

    A ``build`` or ``dgoss run`` that matches no targets is almost always a
    mistake — a typo'd or non-existent ``--image-version``, an over-narrow
    combination of filters, or a ``--dev-versions``/``--matrix-versions``
    selection that excludes everything. Exiting 0 in that case let broken CI
    jobs pass while building/testing nothing, so fail loudly and echo the
    active filters back to aid debugging.
    """
    if targets:
        return
    active = _describe_active_filters(settings)
    detail = f" matching {active}" if active else ""
    stderr_console.print(
        f"❌ No image targets to {context}{detail}. Check the --image-name, --image-version, "
        "--image-variant, --image-os, and --image-platform filters along with the "
        "--recent, --dev-versions, and --matrix-versions selection.",
        style="error",
    )
    raise typer.Exit(code=1)


def _describe_active_filters(settings: BakerySettings) -> str:
    """Render the set filters as a human-readable ``--flag value`` list."""
    f = settings.filter
    parts = [
        f"--{name} {value!r}"
        for name, value in (
            ("image-name", f.image_name),
            ("image-version", f.image_version),
            ("image-variant", f.image_variant),
            ("image-os", f.image_os),
            ("image-platform", f.image_platform),
            ("recent", settings.recent),
        )
        if value
    ]
    return ", ".join(parts)
