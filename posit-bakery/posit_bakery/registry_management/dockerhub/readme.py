import logging
import os
from pathlib import Path

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.registry_management.dockerhub.api import DockerhubClient

log = logging.getLogger(__name__)

DOCKER_HUB_README_USERNAME_ENV = "DOCKER_HUB_README_USERNAME"
DOCKER_HUB_README_PASSWORD_ENV = "DOCKER_HUB_README_PASSWORD"

# Docker Hub hard-caps the `full_description` field at this many bytes (see
# DockerhubClient.update_full_description). Exceeding it makes Docker Hub return a
# raw HTTP 400; the checks below let callers fail with a clear message instead,
# without needing Docker Hub credentials.
DOCKER_HUB_README_MAX_BYTES = 25_000


def _get_dockerhub_repos(target: ImageTarget) -> set[tuple[str, str]]:
    """Extract unique Docker Hub namespace/repository pairs from an image target's tags."""
    repos = set()
    for tag in target.tags:
        if tag.registry and tag.registry.host == "docker.io" and tag.registry.namespace:
            repos.add((tag.registry.namespace, tag.repository))
    return repos


def _eligible_targets(targets: list[ImageTarget]) -> list[tuple[ImageTarget, set[tuple[str, str]]]]:
    """Filter to targets eligible for a Docker Hub README push or length check.

    Eligible targets are non-development versions that are either marked latest
    or a matrix version, and have at least one Docker Hub registry tag.
    """
    eligible: list[tuple[ImageTarget, set[tuple[str, str]]]] = []
    for target in targets:
        if target.image_version.isDevelopmentVersion:
            continue
        if not target.image_version.isMatrixVersion and not target.is_latest:
            continue
        repos = _get_dockerhub_repos(target)
        if not repos:
            continue
        eligible.append((target, repos))
    return eligible


def check_readme_length(content: str, max_bytes: int = DOCKER_HUB_README_MAX_BYTES) -> int:
    """Check README content against Docker Hub's `full_description` byte limit.

    Docker Hub counts the UTF-8 encoded size of the field, not the character count,
    so multi-byte characters can push a README over the limit sooner than a naive
    ``len(content)`` would suggest.

    :param content: The README content to measure.
    :param max_bytes: Maximum allowed size in bytes.
    :return: The number of bytes by which ``content`` exceeds ``max_bytes``, or 0 if
        it is within the limit.
    """
    size = len(content.encode("utf-8"))
    return max(0, size - max_bytes)


def _find_oversized_readmes(
    eligible: list[tuple[ImageTarget, set[tuple[str, str]]]],
    max_bytes: int = DOCKER_HUB_README_MAX_BYTES,
) -> list[str]:
    """Check each eligible target's README.md against Docker Hub's length limit.

    Reads only local files already present in the checkout -- no Docker Hub
    credentials or network access required.

    :return: Human-readable error messages, one per oversized README. Empty if none.
    """
    checked: set[Path] = set()
    violations: list[str] = []
    for target, _repos in eligible:
        readme_path = target.context.image_path / "README.md"
        if readme_path in checked or not readme_path.is_file():
            continue
        checked.add(readme_path)

        over_by = check_readme_length(readme_path.read_text(), max_bytes)
        if over_by:
            size = max_bytes + over_by
            violations.append(
                f"{readme_path} is {size:,} bytes, exceeding Docker Hub's {max_bytes:,}-byte "
                f"README limit by {over_by:,} bytes"
            )
    return violations


def find_oversized_readmes(targets: list[ImageTarget], max_bytes: int = DOCKER_HUB_README_MAX_BYTES) -> list[str]:
    """Check all Docker-Hub-eligible targets' README.md files against the length limit.

    This is a pure, local check: it requires no Docker Hub credentials and makes no
    network calls, so it is safe to run in fork PR CI where secrets are not available
    (see ``bakery ci readme --check``).

    :param targets: List of image targets to evaluate.
    :param max_bytes: Maximum allowed size in bytes (Docker Hub hard limit: 25,000).
    :return: Human-readable error messages, one per oversized README. Empty if all
        eligible READMEs are within the limit.
    """
    return _find_oversized_readmes(_eligible_targets(targets), max_bytes)


def push_readmes(targets: list[ImageTarget]) -> int:
    """Push READMEs to Docker Hub for eligible image targets.

    Pushes the README.md from each image directory to the corresponding Docker Hub
    repository description. Only pushes for targets that are:

    - Marked as latest, or a matrix version
    - Not a development version
    - Have Docker Hub registry tags

    Pushes once per Docker Hub repository, regardless of how many targets share it.

    Requires DOCKER_HUB_README_USERNAME and DOCKER_HUB_README_PASSWORD environment
    variables to be set. Skips gracefully if credentials are not configured.
    Raises on authentication or push failures.

    :param targets: List of image targets to evaluate.
    :return: Number of READMEs pushed.
    :raises ValueError: If one or more eligible READMEs exceed Docker Hub's length limit.
    :raises RuntimeError: If one or more README pushes fail.
    """
    eligible = _eligible_targets(targets)

    if not eligible:
        log.info("No eligible targets for Docker Hub README push.")
        return 0

    violations = _find_oversized_readmes(eligible)
    if violations:
        raise ValueError("README(s) exceed Docker Hub's length limit:\n- " + "\n- ".join(violations))

    username = os.getenv(DOCKER_HUB_README_USERNAME_ENV)
    password = os.getenv(DOCKER_HUB_README_PASSWORD_ENV)
    if not username or not password:
        log.warning(
            f"Docker Hub README credentials not configured "
            f"({DOCKER_HUB_README_USERNAME_ENV}, {DOCKER_HUB_README_PASSWORD_ENV}). "
            f"Skipping README push."
        )
        return 0

    try:
        client = DockerhubClient(identifier=username, secret=password)
    except Exception as e:
        raise RuntimeError(f"Failed to authenticate with Docker Hub: {e}") from e

    pushed: set[str] = set()
    errors: list[str] = []
    for target, repos in eligible:
        readme_path = target.context.image_path / "README.md"
        if not readme_path.is_file():
            log.debug(f"No README.md found at {readme_path}")
            continue

        readme_content = readme_path.read_text()

        for namespace, repository in repos:
            key = f"{namespace}/{repository}"
            if key in pushed:
                continue

            try:
                client.update_full_description(namespace, repository, readme_content)
                log.info(f"Pushed README to Docker Hub for {key}")
                pushed.add(key)
            except Exception as e:
                log.error(f"Failed to push README to Docker Hub for {key}: {e}")
                errors.append(key)

    if errors:
        raise RuntimeError(f"Failed to push READMEs for: {', '.join(errors)}")

    return len(pushed)
