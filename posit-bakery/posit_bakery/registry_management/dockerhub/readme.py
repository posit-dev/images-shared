import logging
import os
import subprocess

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.registry_management.dockerhub.api import DockerhubClient

log = logging.getLogger(__name__)

DOCKERHUB_README_USERNAME_ENV = "DOCKERHUB_README_USERNAME"
DOCKERHUB_README_PASSWORD_ENV = "DOCKERHUB_README_PASSWORD"


def _is_main_branch() -> bool:
    """Check if the current git branch is main.

    Checks the GITHUB_REF_NAME environment variable first (for CI), then falls back to git.
    """
    branch = os.getenv("GITHUB_REF_NAME")
    if branch:
        return branch == "main"

    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() == "main"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _get_dockerhub_repos(target: ImageTarget) -> set[tuple[str, str]]:
    """Extract unique Docker Hub namespace/repository pairs from an image target's tags."""
    repos = set()
    for tag in target.tags:
        if tag.registry and tag.registry.host == "docker.io" and tag.registry.namespace:
            repos.add((tag.registry.namespace, tag.repository))
    return repos


def push_readmes(targets: list[ImageTarget]) -> None:
    """Push READMEs to Docker Hub for eligible image targets.

    Pushes the README.md from each image directory to the corresponding Docker Hub
    repository description. Only pushes when all conditions are met:

    - The current branch is main
    - The image version is marked as latest, or is a matrix version
    - The image version is not a development version
    - The image has Docker Hub registry tags
    - Docker Hub README credentials are configured

    Pushes once per Docker Hub repository, regardless of how many targets share it.

    Failures are logged as warnings and do not raise exceptions.

    :param targets: List of image targets from the current build or merge operation.
    """
    if not _is_main_branch():
        log.debug("Not on main branch, skipping Docker Hub README push.")
        return

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
        log.debug("No eligible targets for Docker Hub README push.")
        return

    username = os.getenv(DOCKERHUB_README_USERNAME_ENV)
    password = os.getenv(DOCKERHUB_README_PASSWORD_ENV)
    if not username or not password:
        log.debug(
            f"Docker Hub README credentials not configured "
            f"({DOCKERHUB_README_USERNAME_ENV}, {DOCKERHUB_README_PASSWORD_ENV}). "
            f"Skipping README push."
        )
        return

    try:
        client = DockerhubClient(identifier=username, secret=password)
    except Exception:
        log.warning("Failed to authenticate with Docker Hub for README push.", exc_info=True)
        return

    pushed: set[str] = set()
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
            except Exception:
                log.warning(f"Failed to push README to Docker Hub for {key}", exc_info=True)
