"""CI matrix generation from selected targets.

Converts a list of ImageTarget objects into the JSON matrix structure consumed
by GitHub Actions workflows.
"""

from enum import Enum

from posit_bakery.image.image_target import ImageTarget


class BakeryCIMatrixFieldEnum(str, Enum):
    VERSION = "version"
    DEV = "dev"
    LATEST = "latest"
    PLATFORM = "platform"


def matrix_rows(
    targets: list[ImageTarget], exclude: list[BakeryCIMatrixFieldEnum] | None = None
) -> list[dict[str, str | bool]]:
    """Generate CI matrix rows from image targets.

    Generates one row per unique (image, version, platform) combination.
    Variant distinctions are not reflected in the matrix; different variants
    of the same version are collapsed into a single row.

    :param targets: List of ImageTarget objects to convert.
    :param exclude: List of fields to exclude from the matrix output.
    :return: List of dictionaries suitable for GitHub Actions matrix output.
    """
    if exclude is None:
        exclude = []

    # Group targets by (image, version) to deduplicate variants
    seen_combinations: set[tuple[str, str, str]] = set()
    data: list[dict[str, str | bool]] = []

    for target in targets:
        # Build the base entry for this target
        entry: dict[str, str | bool] = {"image": target.image_name}

        if BakeryCIMatrixFieldEnum.VERSION not in exclude:
            entry["version"] = target.image_version.name
        if BakeryCIMatrixFieldEnum.DEV not in exclude:
            entry["dev"] = target.image_version.isDevelopmentVersion
        if BakeryCIMatrixFieldEnum.LATEST not in exclude:
            entry["latest"] = target.image_version.is_latest_release

        # Generate rows for each platform (if platforms are not excluded)
        if BakeryCIMatrixFieldEnum.PLATFORM not in exclude:
            for platform in target.image_version.supported_platforms:
                # Deduplicate by (image, version, platform)
                key = (target.image_name, target.image_version.name, platform)
                if key in seen_combinations:
                    continue
                seen_combinations.add(key)

                entry["platform"] = platform
                data.append(entry.copy())
        else:
            # Without platforms, deduplicate by (image, version)
            key = (target.image_name, target.image_version.name, "")
            if key not in seen_combinations:
                seen_combinations.add(key)
                data.append(entry.copy())

    return data
