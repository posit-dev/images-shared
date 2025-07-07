import logging
import re
from typing import Dict, Annotated

from pydantic import BaseModel, ConfigDict, field_validator, Field

from posit_bakery.models.manifest.snyk import ManifestSnyk
from posit_bakery.models.manifest.build import ManifestBuild
from posit_bakery.models.manifest.target import ManifestTarget

log = logging.getLogger(__name__)

# To standardize our images, we will only allow a subset of the regexes
# https://github.com/containers/image/blob/main/docker/reference/regexp.go

# Only allow lowercase letters and hyphens
RE_IMAGE_NAME: re.Pattern = re.compile("^[a-z][a-z-]+$")


class ManifestDocument(BaseModel):
    """Document model for a manifest.yaml file

    Example:

        image_name = "test-image"

        [build."1.0.0"]
        os = ["Ubuntu 24.04", "Ubuntu 22.04"]
        latest = true

        [target.min]

        [target.std]
        [target.std.goss]
        command = "bash"
        wait = 1
    """

    model_config = ConfigDict(frozen=True)

    image_name: str
    build: Dict[str, ManifestBuild] = {}
    target: Dict[str, ManifestTarget] = {}
    snyk: Annotated[ManifestSnyk, Field(default_factory=ManifestSnyk)]

    @field_validator("image_name", mode="after")
    @classmethod
    def validate_image_name(
        cls,
        image_name: str,
    ) -> str:
        if not RE_IMAGE_NAME.match(image_name):
            log.error(f"Invalid image name {image_name}.")
            raise ValueError(f"image_name must only contain lowercase letters and hyphens: {image_name}")

        return image_name
