import logging
from enum import Enum

from posit_bakery.config.image.build_os import DEFAULT_PLATFORMS
from posit_bakery.image.image_target import ImageTarget

log = logging.getLogger(__name__)


class CIMatrixField(str, Enum):
    VERSION = "version"
    DEV = "dev"
    PLATFORM = "platform"


def ci_matrix(
    targets: list[ImageTarget],
    exclude: list[CIMatrixField] | None = None,
) -> list[dict]:
    """Build a CI matrix from resolved image targets.

    The matrix is deduplicated by (image, version, platform) — variants and OS
    entries are not separate matrix dimensions since those are resolved at build
    time.

    :param targets: Image targets to include in the matrix.
    :param exclude: Fields to omit from each matrix entry.
    :return: A list of dicts, one per unique (image, version, platform) combination.
    """
    if exclude is None:
        exclude = []

    seen: set[tuple] = set()
    data = []
    for target in targets:
        version_name = target.image_version.name
        is_dev = target.image_version.isDevelopmentVersion
        platforms = target.image_os.platforms if target.image_os else DEFAULT_PLATFORMS

        if CIMatrixField.PLATFORM not in exclude:
            for platform in platforms:
                key = (target.image_name, version_name, platform)
                if key in seen:
                    continue
                seen.add(key)

                entry = {"image": target.image_name}
                if CIMatrixField.VERSION not in exclude:
                    entry["version"] = version_name
                if CIMatrixField.DEV not in exclude:
                    entry["dev"] = is_dev
                entry["platform"] = platform
                data.append(entry)
        else:
            key = (target.image_name, version_name)
            if key in seen:
                continue
            seen.add(key)

            entry = {"image": target.image_name}
            if CIMatrixField.VERSION not in exclude:
                entry["version"] = version_name
            if CIMatrixField.DEV not in exclude:
                entry["dev"] = is_dev
            data.append(entry)

    return data
