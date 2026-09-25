"""Registry cleanup operations for image caches and temporary images."""

from datetime import timedelta
from typing import Callable

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.registry_management import ghcr


def _clean_registries(
    targets: list[ImageTarget],
    registry_name: Callable[[ImageTarget], str | None],
    remove_untagged: bool,
    remove_older_than: timedelta | None,
    dry_run: bool,
) -> list[Exception]:
    """Cleans up the registries named by ``registry_name`` for all given image targets."""
    # dict.fromkeys, not set(), so cleanup order is deterministic (first-seen).
    target_registries = dict.fromkeys(registry_name(target) for target in targets)

    errors = []
    for registry in target_registries:
        errors.extend(
            ghcr.clean_temporary_artifacts(
                ghcr_registry=registry,
                remove_untagged=remove_untagged,
                remove_older_than=remove_older_than,
                dry_run=dry_run,
            )
        )

    return errors


def clean_caches(
    targets: list[ImageTarget],
    remove_untagged: bool = True,
    remove_older_than: timedelta | None = None,
    dry_run: bool = False,
) -> list[Exception]:
    """Cleans up dangling caches in the specified registry for all given image targets.

    :param targets: List of ImageTarget objects whose caches should be cleaned.
    :param remove_untagged: If True, remove untagged caches.
    :param remove_older_than: Optional timedelta to remove caches older than the specified duration.
    :param dry_run: If True, print what would be deleted without actually deleting anything.
    :return: List of errors encountered during cleanup.
    """
    return _clean_registries(
        targets,
        registry_name=lambda target: cn.split(":")[0] if (cn := target.cache_name()) else None,
        remove_untagged=remove_untagged,
        remove_older_than=remove_older_than,
        dry_run=dry_run,
    )


def clean_temporary(
    targets: list[ImageTarget],
    remove_untagged: bool = True,
    remove_older_than: timedelta | None = None,
    dry_run: bool = False,
) -> list[Exception]:
    """Cleans up temporary images in the specified registry for all given image targets.

    :param targets: List of ImageTarget objects whose temporary images should be cleaned.
    :param remove_untagged: If True, remove untagged images.
    :param remove_older_than: Optional timedelta to remove images older than the specified duration.
    :param dry_run: If True, print what would be deleted without actually deleting anything.
    :return: List of errors encountered during cleanup.
    """
    return _clean_registries(
        targets,
        registry_name=lambda target: target.temp_name,
        remove_untagged=remove_untagged,
        remove_older_than=remove_older_than,
        dry_run=dry_run,
    )
