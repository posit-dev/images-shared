import logging
import os
import subprocess
from pathlib import Path

import python_on_whales

from posit_bakery.image.image_target import ImageTarget
from posit_bakery.plugins.builtin.wizcli.command import find_wizcli_bin

log = logging.getLogger(__name__)


def _destination_tags(target: ImageTarget) -> list[str]:
    """Return one deterministic local tag for each final repository."""
    tags_by_destination: dict[str, str] = {}
    for tag in target.tags:
        if tag.destination:
            tags_by_destination.setdefault(tag.destination, str(tag))
    return [tags_by_destination[destination] for destination in sorted(tags_by_destination)]


def tag_published_repositories(
    context: Path,
    targets: list[ImageTarget],
    *,
    platform: str,
    projects: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> list[str]:
    """Associate locally scanned digests with their future registry repositories.

    Each built image is given a local alias in every configured final repository.
    ``--digest`` tells Wiz which locally scanned artifact that repository name
    represents. The aliases do not need to exist remotely yet; publishing later
    preserves the content-addressed platform digest.

    Returns human-readable failures so callers can report all destinations rather
    than stopping after the first failure.
    """
    wizcli_bin = find_wizcli_bin(context)
    run_env = os.environ.copy()
    if client_id:
        run_env["WIZ_CLIENT_ID"] = client_id
    if client_secret:
        run_env["WIZ_CLIENT_SECRET"] = client_secret

    failures: list[str] = []
    attempts = 0

    for target in targets:
        metadata = target.build_metadata_for_platform(platform)
        if metadata is None or not metadata.container_image_digest or not metadata.digest_ref:
            failures.append(f"{target}: no build digest for {platform}")
            continue

        digest = metadata.container_image_digest
        source_ref = metadata.digest_ref
        destination_tags = _destination_tags(target)
        if not destination_tags:
            failures.append(f"{target}: no final repository tags")
            continue

        # An explicit --projects always wins over bakery.yaml, since CI feeds this from a
        # secret and bakery.yaml never should. Mirrors WizCLICommand.command's own precedence.
        tool_options = target.get_tool_option("wizcli")
        target_projects = projects or (
            ",".join(tool_options.projects) if tool_options and tool_options.projects else None
        )

        for destination_tag in destination_tags:
            attempts += 1
            try:
                python_on_whales.docker.image.tag(source_ref, destination_tag)
            except python_on_whales.exceptions.DockerException as exc:
                failures.append(f"{target}: could not create local alias {destination_tag}: {exc}")
                continue

            cmd = [wizcli_bin, "tag", destination_tag, "--digest", digest, "--no-color", "--no-style"]
            if target_projects:
                cmd.extend(["--projects", target_projects])

            result = subprocess.run(
                cmd,
                cwd=context,
                env=run_env,
                capture_output=True,
                text=True,
                check=False,
            )  # noqa: S603
            if result.returncode != 0:
                output = result.stdout.strip() or result.stderr.strip()
                failures.append(f"{target}: wizcli tag failed for {destination_tag}@{digest}: {output}")
                continue

            log.info(f"Tagged {destination_tag}@{digest} in Wiz")

    if attempts == 0 and not failures:
        failures.append("No Wiz tag operations were attempted")

    return failures
