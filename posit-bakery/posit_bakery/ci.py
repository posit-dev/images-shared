import glob
import logging
from enum import Enum
from pathlib import Path

from posit_bakery.config.image.build_os import DEFAULT_PLATFORMS
from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.protocol import ToolCallResult

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


def resolve_metadata_globs(metadata_files: list[Path]) -> list[Path]:
    """Resolve glob patterns in metadata file paths.

    :param metadata_files: Paths that may contain glob patterns.
    :return: Resolved absolute paths.
    """
    resolved: list[Path] = []
    for file in metadata_files:
        if "*" in str(file) or "?" in str(file) or "[" in str(file):
            resolved.extend(sorted(Path(x).absolute() for x in glob.glob(str(file))))
        else:
            resolved.append(file.absolute())
    return resolved


def ci_merge(
    base_path: Path,
    targets: list[ImageTarget],
    metadata_files: list[Path],
    load_metadata: callable,
    dry_run: bool = False,
) -> list[ToolCallResult]:
    """Merge platform-specific builds into multi-platform manifests.

    :param base_path: Root path of the bakery project.
    :param targets: Resolved image targets with metadata loaded.
    :param metadata_files: Paths to build metadata JSON files.
    :param load_metadata: Callable that loads metadata from a file path,
        returning a list of loaded target UIDs. Typically
        BakeryConfig.load_build_metadata_from_file.
    :param dry_run: If True, do not push merged images.
    :return: List of tool call results from the merge operation.
    :raises RuntimeError: If any metadata files fail to load.
    """
    resolved_files = resolve_metadata_globs(metadata_files)

    log.info(f"Reading targets from {', '.join(f.name for f in resolved_files)}")

    errors = []
    loaded_targets: list[str] = []
    for file in resolved_files:
        try:
            loaded_targets.extend(load_metadata(file))
        except Exception as e:
            log.error(f"Failed to load metadata from file '{file}'")
            log.error(str(e))
            errors.append(e)
    loaded_targets = list(set(loaded_targets))

    if errors:
        raise RuntimeError("One or more metadata files are invalid, aborting merge.")

    log.info(f"Found {len(loaded_targets)} targets")
    log.debug(", ".join(loaded_targets))

    from posit_bakery.plugins.registry import get_plugin

    oras = get_plugin("oras")
    results = oras.execute(base_path, targets, dry_run=dry_run)
    oras.results(results)

    return results
