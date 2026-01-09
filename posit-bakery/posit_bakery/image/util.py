import subprocess

import python_on_whales

from posit_bakery.image.image_metadata import ImageToolsInspectionMetadata


def inspect_image(image_ref: str) -> ImageToolsInspectionMetadata:
    """Inspects a container image using `imagetools inspect` and returns the metadata.

    This implementation uses subprocess to call the Docker CLI directly, as python-on-whales does not currently
    properly support inspection of index-based images.

    :param image_ref: The image reference to inspect

    :return: The image inspection metadata
    """
    command = [str(x) for x in python_on_whales.docker.docker_cmd]
    command.extend(["buildx", "imagetools", "inspect", image_ref, "--format", "{{json .Manifest}}"])
    p = subprocess.run(command, capture_output=True)
    inspection_metadata = ImageToolsInspectionMetadata.model_validate_json(p.stdout.decode())

    return inspection_metadata
