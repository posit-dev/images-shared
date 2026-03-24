import logging
import os

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.registry_management.dockerhub.api import DockerhubClient

log = logging.getLogger(__name__)

DOCKERHUB_README_USERNAME_ENV = "DOCKERHUB_README_USERNAME"
DOCKERHUB_README_PASSWORD_ENV = "DOCKERHUB_README_PASSWORD"


def _get_dockerhub_repos(target: ImageTarget) -> set[tuple[str, str]]:
    """Extract unique Docker Hub namespace/repository pairs from an image target's tags."""
    repos = set()
    for tag in target.tags:
        if tag.registry and tag.registry.host == "docker.io" and tag.registry.namespace:
            repos.add((tag.registry.namespace, tag.repository))
    return repos


def push_readmes(targets: list[ImageTarget]) -> int:
    """Push READMEs to Docker Hub for eligible image targets.

    Pushes the README.md from each image directory to the corresponding Docker Hub
    repository description. Only pushes for targets that are:

    - Marked as latest, or a matrix version
    - Not a development version
    - Have Docker Hub registry tags

    Pushes once per Docker Hub repository, regardless of how many targets share it.

    Requires DOCKERHUB_README_USERNAME and DOCKERHUB_README_PASSWORD environment
    variables to be set. Skips gracefully if credentials are not configured.
    Raises on authentication or push failures.

    :param targets: List of image targets to evaluate.
    :return: Number of READMEs pushed.
    :raises RuntimeError: If one or more README pushes fail.
    """
    eligible: list[ImageTarget] = []
    for target in targets:
        if target.image_version.isDevelopmentVersion:
            continue
        if not target.image_version.isMatrixVersion and not target.is_latest:
            continue
        if not _get_dockerhub_repos(target):
            continue
        eligible.append(target)

    if not eligible:
        log.info("No eligible targets for Docker Hub README push.")
        return 0

    username = os.getenv(DOCKERHUB_README_USERNAME_ENV)
    password = os.getenv(DOCKERHUB_README_PASSWORD_ENV)
    if not username or not password:
        log.warning(
            f"Docker Hub README credentials not configured "
            f"({DOCKERHUB_README_USERNAME_ENV}, {DOCKERHUB_README_PASSWORD_ENV}). "
            f"Skipping README push."
        )
        return 0

    client = DockerhubClient(identifier=username, secret=password)

    pushed: set[str] = set()
    errors: list[str] = []
    for target in eligible:
        readme_path = target.context.image_path / "README.md"
        if not readme_path.is_file():
            log.debug(f"No README.md found at {readme_path}")
            continue

        readme_content = readme_path.read_text()

        for namespace, repository in _get_dockerhub_repos(target):
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
