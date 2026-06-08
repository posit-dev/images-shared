import logging
from datetime import timedelta

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.registry_management import ghcr

log = logging.getLogger(__name__)


def clean_caches(
    targets: list[ImageTarget],
    remove_untagged: bool = True,
    remove_older_than: timedelta | None = None,
    dry_run: bool = False,
) -> list[Exception]:
    """Clean up dangling caches in the registry for the given image targets.

    :param targets: Image targets whose cache registries should be cleaned.
    :param remove_untagged: If True, remove untagged caches.
    :param remove_older_than: Remove caches older than the specified duration.
    :param dry_run: If True, print what would be deleted without deleting.
    :return: List of errors encountered during cleanup.
    """
    target_caches = list(set([cn.split(":")[0] for target in targets if (cn := target.cache_name())]))

    errors = []
    for target_cache in target_caches:
        errors.extend(
            ghcr.clean_temporary_artifacts(
                ghcr_registry=target_cache,
                remove_untagged=remove_untagged,
                remove_older_than=remove_older_than,
                dry_run=dry_run,
            )
        )

    return errors


def clean_temporary(
    targets: list[ImageTarget],
    remove_untagged: bool = True,
    remove_older_than: timedelta | None = None,
    dry_run: bool = False,
) -> list[Exception]:
    """Clean up temporary images in the registry for the given image targets.

    :param targets: Image targets whose temporary registries should be cleaned.
    :param remove_untagged: If True, remove untagged images.
    :param remove_older_than: Remove images older than the specified duration.
    :param dry_run: If True, print what would be deleted without deleting.
    :return: List of errors encountered during cleanup.
    """
    target_caches = list(set([target.temp_name for target in targets]))

    errors = []
    for target_cache in target_caches:
        errors.extend(
            ghcr.clean_temporary_artifacts(
                ghcr_registry=target_cache,
                remove_untagged=remove_untagged,
                remove_older_than=remove_older_than,
                dry_run=dry_run,
            )
        )

    return errors
