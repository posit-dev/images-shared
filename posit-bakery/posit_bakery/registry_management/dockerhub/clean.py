import logging
import re
from datetime import timedelta, datetime

from posit_bakery.registry_management.dockerhub.api import DockerhubClient

log = logging.getLogger(__name__)
REGISTRY_PATTERN = re.compile(r"docker\.io/(?P<namespace>[A-Za-z0-9_.-]+)/(?P<repository>[A-Za-z0-9_./-]+)")


def clean_registry(
    image_registry: str,
    remove_tagged_older_than: timedelta | None = timedelta(weeks=80),
    remove_untagged_older_than: timedelta | None = timedelta(weeks=26),
):
    """Cleans up images in the specified registry."""
    # Check that the registry matches the expected pattern.
    match = REGISTRY_PATTERN.match(image_registry)
    if not match:
        raise ValueError(f"Invalid Docker Hub registry format: {image_registry}")
    namespace = match.group("namespace")
    repository = match.group("repository")

    client = DockerhubClient()
    tags = client.get_tags(namespace, repository)

    filtered_tags = []
    for tag in tags:
        if remove_tagged_older_than is not None:
            last_updated = datetime.fromisoformat(tag.get("last_updated"))
            if last_updated < datetime.now() - remove_tagged_older_than:
                filtered_tags.append(tag)
        if remove_untagged_older_than is not None and tag.get("tag_status") == "inactive":
            last_updated = datetime.fromisoformat(tag.get("last_updated"))
            if last_updated < datetime.now() - remove_untagged_older_than:
                filtered_tags.append(tag)

    log.info(f"Removing {len(filtered_tags)} tagged images from {image_registry}")
    for tag in filtered_tags:
        client.delete_tag(namespace, repository, tag.get("tag_id"))
